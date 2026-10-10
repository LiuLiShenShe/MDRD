from __future__ import annotations

import re
import shutil
import sqlite3
import uuid
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pycolmap

from mdrd.common import capture, manifest_image_inputs, read_json, run_command, sha256, stage, write_json


PAIR_ID_FACTOR = 2147483647


def decode_pair(pair_id):
    return pair_id // PAIR_ID_FACTOR, pair_id % PAIR_ID_FACTOR


def database_statistics(database, directory):
    with sqlite3.connect(database) as connection:
        images = pd.read_sql_query("SELECT image_id,name,camera_id FROM images", connection)
        features = pd.read_sql_query("SELECT image_id,rows AS sift_features FROM keypoints", connection)
        raw = dict(connection.execute("SELECT pair_id,rows FROM matches"))
        verified = dict(connection.execute("SELECT pair_id,rows FROM two_view_geometries"))
    records = []
    names = images.set_index("image_id").name.to_dict()
    for pair_id in sorted(set(raw) | set(verified)):
        first, second = decode_pair(pair_id)
        records.append({"image_id_i": first, "image_id_j": second, "filename_i": names[first], "filename_j": names[second], "match_count": raw.get(pair_id, np.nan), "verified_match_count": verified.get(pair_id, 0)})
    columns = ["image_id_i", "image_id_j", "filename_i", "filename_j", "match_count", "verified_match_count"]
    pairs = pd.DataFrame(records, columns=columns)
    pairs.to_csv(Path(directory) / "database_pairs.csv", index=False)
    features = images.merge(features, how="left", on="image_id")
    features.to_csv(Path(directory) / "database_images.csv", index=False)
    return features, pairs


def models_at(root):
    root = Path(root)
    models = []
    candidates = [root] + list(root.glob("*")) if root.exists() else []
    for path in candidates:
        if not path.is_dir() or not ((path / "images.bin").exists() or (path / "images.txt").exists()):
            continue
        try:
            reconstruction = pycolmap.Reconstruction(path)
            models.append((path, reconstruction))
        except Exception as exception:
            print(f"MODEL_READ_FAILURE {path}: {exception}", flush=True)
    return models


def model_summary(path, reconstruction):
    errors = [point.error for point in reconstruction.points3D.values() if np.isfinite(point.error)]
    tracks = [point.track.length() for point in reconstruction.points3D.values()]
    cameras = [{"camera_id": camera.camera_id, "model": camera.model_name, "width": camera.width, "height": camera.height, "params": camera.params.tolist(), "focal_to_max_dimension": camera.mean_focal_length() / max(camera.width, camera.height), "bogus_parameters": camera.has_bogus_params(.1, 10, 1)} for camera in reconstruction.cameras.values()]
    return {"path": str(path), "registered_images": reconstruction.num_reg_images(), "registered_filenames": [reconstruction.images[image_id].name for image_id in reconstruction.reg_image_ids()], "num_3d_points": reconstruction.num_points3D(), "mean_reprojection_error": np.mean(errors) if errors else None, "median_reprojection_error": np.median(errors) if errors else None, "track_length_distribution": {str(length): tracks.count(length) for length in sorted(set(tracks))}, "cameras": cameras}


def run_sfm(directory, configuration, force=False):
    directory = Path(directory)
    output = directory / "sfm"
    parameters = configuration["sfm"]
    manifest_path = directory / "frame_manifest.csv"
    labels_path = directory / "segments" / "coarse_frame_labels.csv"
    quality_path = directory / "quality" / "frame_quality.csv"
    def required_outputs():
        required = [output / "sfm_summary.json", output / "database.db", output / "database_images.csv", output / "database_pairs.csv", output / "sfm_image_manifest.csv"]
        if (output / "sfm_summary.json").exists():
            previous_model = read_json(output / "sfm_summary.json").get("model_path")
            if previous_model:
                required += [Path(previous_model) / f"{name}.bin" for name in ("cameras", "images", "points3D")]
        return required
    with stage(directory, "sfm", parameters, [manifest_path, labels_path, quality_path, *manifest_image_inputs(manifest_path)], force, required_outputs=required_outputs) as execute:
        if not execute:
            return read_json(output / "sfm_summary.json")
        if output.exists():
            archive = directory / "sfm_previous"
            if archive.exists():
                archive = directory / "sfm_history" / f"run_{uuid.uuid4().hex[:12]}"
                archive.parent.mkdir(exist_ok=True)
            output.rename(archive)
        output.mkdir(exist_ok=True)
        logs = output / "logs"
        logs.mkdir(exist_ok=True)
        executable = parameters["executable"]
        help_text = {}

        def command(name, arguments, log_name=None, allow_failure=False):
            if name not in help_text:
                help_text[name] = capture([executable, name, "-h"])["text"]
                (logs / f"{name}_help.txt").write_text(help_text[name])
            flags = arguments + sum(([str(key), str(value)] for key, value in parameters.get("extra_options", {}).get(name, {}).items()), [])
            for item in flags:
                if str(item).startswith("--") and str(item)[2:] not in help_text[name]:
                    raise ValueError(f"Installed {name} does not support {item}")
            return run_command([executable, name] + flags, logs / (log_name or f"{name}.log"), allow_failure, timeout=parameters.get("command_timeout_sec"))

        manifest = pd.read_csv(manifest_path)
        sfm_images = directory / "sfm_images"
        sfm_images.mkdir(exist_ok=True)
        conversion = []
        for item in manifest.to_dict("records"):
            destination = sfm_images / item["filename"]
            image = cv2.imread(item["image_path"], cv2.IMREAD_UNCHANGED)
            if image is None:
                raise RuntimeError(f"Unreadable source frame {item['image_path']}")
            source_dtype = str(image.dtype)
            if image.dtype == np.uint16:
                image = np.right_shift(image, 8).astype(np.uint8)
            elif image.dtype != np.uint8:
                raise ValueError(f"Unsupported source pixel type {image.dtype}")
            if not cv2.imwrite(str(destination), image):
                raise RuntimeError(f"Cannot write SfM image {destination}")
            conversion.append({"filename": item["filename"], "source_path": item["image_path"], "source_sha256": item["file_sha256"], "sfm_path": str(destination.resolve()), "sfm_sha256": sha256(destination), "source_dtype": source_dtype, "sfm_dtype": "uint8", "conversion": "uint16 >> 8, no HDR tone mapping" if source_dtype == "uint16" else "identity pixels, lossless PNG container", "width": image.shape[1], "height": image.shape[0]})
        pd.DataFrame(conversion).to_csv(output / "sfm_image_manifest.csv", index=False)
        coarse = pd.read_csv(labels_path)
        quality = pd.read_csv(quality_path)
        merged = coarse.merge(quality[["filename", "quality_label", "feature_count", "feature_coverage"]], on="filename")
        global_names = merged.loc[(merged.label == "GLOBAL") & (merged.feature_count >= 100) & (merged.feature_coverage >= .35), "filename"].tolist()
        global_list = output / "global_images.txt"
        global_list.write_text("\n".join(global_names) + "\n")
        all_list = output / "all_images.txt"
        all_list.write_text("\n".join(manifest.filename) + "\n")
        database = output / "database.db"
        if database.exists():
            database.unlink()
        command("feature_extractor", ["--database_path", str(database), "--image_path", str(sfm_images), "--image_list_path", str(all_list), "--ImageReader.camera_model", parameters["camera_model"], "--ImageReader.single_camera", "1", "--SiftExtraction.use_gpu", str(int(parameters["use_gpu"])), "--SiftExtraction.num_threads", str(parameters["threads"]), "--SiftExtraction.max_image_size", str(parameters["max_image_size"]), "--SiftExtraction.max_num_features", str(parameters["max_num_features"])])
        with sqlite3.connect(database) as connection:
            extracted = connection.execute("SELECT COUNT(*) FROM keypoints WHERE rows>0").fetchone()[0]
        if extracted < 2:
            raise RuntimeError("Feature extraction produced fewer than two usable images; see extraction log")
        match_args = ["--database_path", str(database), "--SiftMatching.use_gpu", str(int(parameters["use_gpu"])), "--SiftMatching.num_threads", str(parameters["threads"])]
        if len(manifest) <= parameters["exhaustive_limit"]:
            matching_strategy = "EXHAUSTIVE_ALL_PAIRS"
            command("exhaustive_matcher", match_args)
        else:
            names = manifest.filename.tolist()
            overlap = parameters["sequential_overlap"]
            pairs = set()
            for index, first in enumerate(names):
                for second in names[index + 1:index + 1 + overlap]:
                    pairs.add(tuple(sorted([first, second])))
                for anchor in global_names[::max(1, len(global_names) // 18)]:
                    if anchor != first:
                        pairs.add(tuple(sorted([first, anchor])))
            for index, first in enumerate(global_names):
                for second in global_names[index + 1:]:
                    pairs.add(tuple(sorted([first, second])))
            pair_path = output / "matching_pairs.txt"
            pair_path.write_text("\n".join(" ".join(pair) for pair in sorted(pairs)) + "\n")
            matching_strategy = "SEQUENTIAL_PLUS_GLOBAL_ANCHORS_AND_GLOBAL_LOOP_CLOSURE"
            command("matches_importer", match_args + ["--match_list_path", str(pair_path), "--match_type", "pairs"])
        database_statistics(database, output)
        mapper_args = ["--database_path", str(database), "--image_path", str(sfm_images), "--Mapper.num_threads", str(parameters["threads"])]
        global_models = []
        if len(global_names) >= 5:
            root = output / "global"
            root.mkdir(exist_ok=True)
            command("mapper", mapper_args + ["--image_list_path", str(global_list), "--output_path", str(root)], "mapper_global.log", True)
            global_models = models_at(root)
        global_best = max(global_models, key=lambda item: item[1].num_reg_images()) if global_models else None
        all_models = []
        chosen = None
        strategy = None
        if global_best:
            registered_path = output / "registered"
            registered_path.mkdir(exist_ok=True)
            command("image_registrator", ["--database_path", str(database), "--input_path", str(global_best[0]), "--output_path", str(registered_path), "--Mapper.num_threads", str(parameters["threads"])], allow_failure=True)
            continued = output / "continued"
            continued.mkdir(exist_ok=True)
            starting = registered_path if models_at(registered_path) else global_best[0]
            command("mapper", mapper_args + ["--input_path", str(starting), "--output_path", str(continued), "--Mapper.fix_existing_images", "1"], "mapper_continue.log", True)
            all_models = models_at(continued) + models_at(registered_path)
            candidates = all_models + [global_best]
            chosen = max(candidates, key=lambda item: item[1].num_reg_images())
            strategy = "GLOBAL_FIRST_REGISTRATION_AND_INCREMENTAL_CONTINUATION"
        if (not chosen or chosen[1].num_reg_images() < .85 * len(manifest)) and parameters["joint_fallback"]:
            joint = output / "joint"
            joint.mkdir(exist_ok=True)
            command("mapper", mapper_args + ["--output_path", str(joint)], "mapper_joint.log", True)
            joint_models = models_at(joint)
            all_models += joint_models
            if joint_models:
                best_joint = max(joint_models, key=lambda item: item[1].num_reg_images())
                if not chosen or best_joint[1].num_reg_images() > chosen[1].num_reg_images():
                    chosen = best_joint
                    strategy = "JOINT_FALLBACK_DIFFERENT_GAUGE_NO_ABSOLUTE_BASELINE_COMPARISON"
        summary = {"video_id": directory.name, "total_images": len(manifest), "global_candidates": len(global_names), "matching_strategy": matching_strategy, "strategy": strategy, "global_models": [model_summary(*item) for item in global_models], "other_models": [model_summary(*item) for item in all_models], "global_seed_filenames": model_summary(*global_best)["registered_filenames"] if global_best else [], "pnp_inliers_note": "PnP inlier counts unavailable as structured CLI output; kept missing, not inferred from match counts.", "foreground_note": "No verified foreground masks: reconstructed points may primarily constrain background."}
        if chosen:
            triangulated = output / "triangulated"
            triangulated.mkdir(exist_ok=True)
            command("point_triangulator", ["--database_path", str(database), "--image_path", str(sfm_images), "--input_path", str(chosen[0]), "--output_path", str(triangulated), "--Mapper.num_threads", str(parameters["threads"])], allow_failure=True)
            if models_at(triangulated):
                chosen = models_at(triangulated)[0]
            final = output / "final"
            final.mkdir(exist_ok=True)
            command("bundle_adjuster", ["--input_path", str(chosen[0]), "--output_path", str(final)], allow_failure=True)
            if models_at(final):
                chosen = models_at(final)[0]
            summary["final_model"] = model_summary(*chosen)
            summary["model_path"] = str(chosen[0].resolve())
            summary["status"] = "RECONSTRUCTED_REQUIRES_GEOMETRIC_AUDIT"
        else:
            summary.update(status="INITIALIZATION_FAILURE", model_path=None, final_model=None)
        write_json(output / "sfm_summary.json", summary)
        print(f"SFM {directory.name} {summary['status']} {summary.get('final_model', {}).get('registered_images', 0) if summary.get('final_model') else 0}/{len(manifest)}", flush=True)
        return summary
