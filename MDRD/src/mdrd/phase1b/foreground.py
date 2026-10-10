from __future__ import annotations

from pathlib import Path
from functools import lru_cache
import sqlite3

import cv2
import numpy as np
import pandas as pd
import pycolmap

from mdrd.common import read_json, sha256, stage, write_json
from mdrd.geometry.analysis import read_model_observations
from mdrd.geometry.core import broad_label, covisibility, pair_statistics


UNCERTAIN, PLANT_FOREGROUND, BACKGROUND = 0, 1, 2
VERIFIED_MASK_SOURCES = {"HUMAN_VERIFIED", "MANUAL_OVERRIDE", "EXTERNAL_VERIFIED_ANNOTATION"}


def verified_mask_provenance(entry):
    source = entry.get("source")
    confirmed = entry.get("human_confirmed") is True
    reviewer = bool(entry.get("reviewed_by"))
    if (source in VERIFIED_MASK_SOURCES and not (confirmed and reviewer)) or (confirmed and source not in VERIFIED_MASK_SOURCES):
        raise ValueError("Verified mask requires an authoritative source, human confirmation and a named reviewer")
    return confirmed


def load_mask(path, size):
    mask = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if mask is None or mask.ndim != 2 or mask.dtype != np.uint8:
        raise ValueError(f"Missing or invalid grayscale uint8 mask: {path}")
    if mask.shape != (size[1], size[0]) or not np.isin(mask, [UNCERTAIN, PLANT_FOREGROUND, BACKGROUND]).all():
        raise ValueError(f"Mask size/class/orientation mismatch: {path}; expected {size}")
    return mask


def mask_at_observation(mask, pixel):
    x, y = np.asarray(pixel, dtype=float)
    if not np.isfinite([x, y]).all():
        return UNCERTAIN
    x, y = int(round(x)), int(round(y))
    if x < 0 or y < 0 or x >= mask.shape[1] or y >= mask.shape[0]:
        return UNCERTAIN
    return int(mask[y, x])


def classify_votes(votes):
    foreground = sum(label == PLANT_FOREGROUND for label in votes)
    background = sum(label == BACKGROUND for label in votes)
    unknown = sum(label == UNCERTAIN for label in votes)
    if foreground >= 2 and not background:
        label = "PLANT_FOREGROUND"
    elif background >= 2 and not foreground:
        label = "BACKGROUND"
    else:
        label = "UNCERTAIN"
    return {"class": label, "foreground_observations": foreground, "background_observations": background, "uncertain_observations": unknown, "confidence": max(foreground, background) / (foreground + background + unknown) if votes else None}


def import_mask(image_path, mask_path, destination, source, reviewer=None):
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Missing source image: {image_path}")
    mask = load_mask(mask_path, (image.shape[1], image.shape[0]))
    if source in VERIFIED_MASK_SOURCES and not reviewer:
        raise ValueError("Human-verified masks require named reviewer")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(destination), mask)
    return {"mask_path": str(destination), "mask_sha256": sha256(destination), "image_path": str(image_path), "image_sha256": sha256(image_path), "source": source, "reviewed_by": reviewer, "human_confirmed": bool(source in VERIFIED_MASK_SOURCES and reviewer), "plant_fraction": float(np.mean(mask == PLANT_FOREGROUND)), "background_fraction": float(np.mean(mask == BACKGROUND))}


def make_sam_candidate(image_path, prompt, checkpoint, destination):
    original = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if original is None:
        raise ValueError(f"Unreadable frame: {image_path}")
    height, width = original.shape[:2]
    factor = min(1., 960 / max(height, width))
    image = cv2.resize(original, (round(width * factor), round(height * factor)), interpolation=cv2.INTER_AREA)
    predictor = _predictor(str(checkpoint))
    predictor.set_image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    box = np.asarray(prompt["box_xyxy_normalized"], dtype=float) * np.array([image.shape[1], image.shape[0], image.shape[1], image.shape[0]])
    if not (0 <= box[0] < box[2] <= image.shape[1] and 0 <= box[1] < box[3] <= image.shape[0]):
        raise ValueError("SAM prompt bounding box is invalid")
    masks, scores, _ = predictor.predict(box=box, multimask_output=True)
    index = int(np.argmax(scores))
    candidate = cv2.resize(masks[index].astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST)
    kernel = np.ones((13, 13), np.uint8)
    core = cv2.erode(candidate, kernel)
    mask = np.zeros((height, width), np.uint8)
    mask[core == 1] = PLANT_FOREGROUND
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(destination), mask)
    return {"mask_path": str(destination), "mask_sha256": sha256(destination), "image_path": str(image_path), "image_sha256": sha256(image_path), "source": "PROVISIONAL_AUTO_AGNES_BOX_SAM_VIT_B", "human_confirmed": False, "sam_score_not_ground_truth_iou": float(scores[index]), "plant_fraction": float(np.mean(mask == PLANT_FOREGROUND)), "background_fraction": 0., "note": "Outside candidate and boundaries remain UNCERTAIN; pot and background are not inferred by color or assumed from the box"}


@lru_cache(maxsize=1)
def _predictor(checkpoint):
    from segment_anything import SamPredictor, sam_model_registry
    import torch

    model = sam_model_registry["vit_b"](checkpoint=checkpoint)
    return SamPredictor(model.to("cuda" if torch.cuda.is_available() else "cpu"))


def mask_overlay(image_path, mask, destination):
    image = cv2.imread(str(image_path))
    preview = cv2.resize(image, (640, round(image.shape[0] * 640 / image.shape[1])))
    region = cv2.resize(mask, (preview.shape[1], preview.shape[0]), interpolation=cv2.INTER_NEAREST)
    highlight = preview.copy()
    highlight[region == PLANT_FOREGROUND] = (0, 210, 255)
    highlight[region == BACKGROUND] = (235, 100, 60)
    cv2.imwrite(str(destination), np.concatenate([preview, cv2.addWeighted(preview, .55, highlight, .45, 0)], axis=1))


def analyze_foreground(video_dir, destination, mask_manifest):
    video_dir, destination = Path(video_dir), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    sfm = read_json(video_dir / "sfm" / "sfm_summary.json")
    model_path = Path(sfm["model_path"])
    inputs = [mask_manifest, video_dir / "segments" / "segment_confidence.csv", video_dir / "sfm" / "database.db", *[model_path / f"{name}.bin" for name in ("cameras", "images", "points3D")]]
    manifest = read_json(mask_manifest)
    entries = manifest.get("masks", [])
    inputs += [row["mask_path"] for row in entries]
    with stage(destination, "foreground", {"min_votes": 2, "mask_policy": "three_classes_exact_size", "model": str(model_path)}, inputs, required_outputs=[destination / "summary.json", destination / "point_votes.csv", destination / "per_image_foreground.csv", destination / "foreground_pairs.csv", destination / "mask_review_checklist.md"]) as execute:
        if not execute:
            return read_json(destination / "summary.json")
        reconstruction, poses, points, _, _, _, _ = read_model_observations(model_path)
        labels = pd.read_csv(video_dir / "segments" / "segment_confidence.csv").set_index("filename").label.to_dict()
        masks, entry_by_name = {}, {}
        for entry in entries:
            verified_mask_provenance(entry)
            for key, path in (("image_sha256", entry["image_path"]), ("mask_sha256", entry["mask_path"])):
                if entry.get(key) and entry[key] != sha256(path):
                    raise ValueError(f"Mask manifest {key} does not match {path}")
            name = Path(entry["image_path"]).name
            image_id = next((image_id for image_id, pose in poses.items() if pose["name"] == name), None)
            if image_id is None:
                continue
            camera = poses[image_id]["camera"]
            masks[image_id] = load_mask(entry["mask_path"], (camera.width, camera.height))
            entry_by_name[name] = entry
            mask_overlay(entry["image_path"], masks[image_id], destination / f"overlay_{name}.png")
        rows, foreground_ids = [], set()
        per_image = {image_id: set() for image_id in poses}
        verified_images = {name for name, entry in entry_by_name.items() if verified_mask_provenance(entry)}
        for point_id, point in points.items():
            votes, verified_votes, foreground_observers, observed_images = [], [], set(), set()
            for element in reconstruction.points3D[point_id].track.elements:
                if element.image_id not in point["images"] or element.image_id not in masks or element.image_id in observed_images:
                    continue
                observed_images.add(element.image_id)
                observation = reconstruction.images[element.image_id].points2D[element.point2D_idx]
                vote = mask_at_observation(masks[element.image_id], observation.xy)
                votes.append(vote)
                if vote == PLANT_FOREGROUND:
                    foreground_observers.add(element.image_id)
                if reconstruction.images[element.image_id].name in verified_images:
                    verified_votes.append(vote)
            row = {"point3d_id": point_id, "observing_cameras": len(point["images"]), "mask_observing_cameras": len(votes), "valid_track_length": point["track_length"], "point_reprojection_error": point["error"], **classify_votes(votes), "verified_class": classify_votes(verified_votes)["class"]}
            rows.append(row)
            if row["class"] == "PLANT_FOREGROUND":
                foreground_ids.add(point_id)
                for image_id in foreground_observers:
                    per_image[image_id].add(point_id)
        point_table = pd.DataFrame(rows, columns=["point3d_id", "observing_cameras", "mask_observing_cameras", "valid_track_length", "point_reprojection_error", "class", "foreground_observations", "background_observations", "uncertain_observations", "confidence", "verified_class"])
        point_table.to_csv(destination / "point_votes.csv", index=False)
        image_rows = []
        database = video_dir / "sfm" / "database.db"
        with sqlite3.connect(database if database.exists() else ":memory:") as connection:
            db_ids = {name: image_id for image_id, name in connection.execute("SELECT image_id,name FROM images")} if database.exists() else {}
            for image_id, mask in masks.items():
                name = poses[image_id]["name"]
                db_id = db_ids.get(name)
                feature_count = 0
                if db_id is not None:
                    record = connection.execute("SELECT rows,cols,data FROM keypoints WHERE image_id=?", (db_id,)).fetchone()
                    if record and record[2] is not None:
                        keypoints = np.frombuffer(record[2], dtype=np.float32).reshape(record[0], record[1])
                        feature_count = sum(mask_at_observation(mask, xy) == PLANT_FOREGROUND for xy in keypoints[:, :2])
                pixels = int(np.count_nonzero(mask == PLANT_FOREGROUND))
                image_rows.append({"filename": name, "stage": broad_label(labels.get(name)), "mask_source": entry_by_name[name]["source"], "mask_human_verified": name in verified_images, "plant_pixel_fraction_candidate": pixels / mask.size, "plant_sift_features_candidate": int(feature_count), "plant_feature_density_per_megapixel_candidate": feature_count / pixels * 1e6 if pixels else None, "foreground_valid_sparse_points_candidate": len(per_image[image_id])})
        pd.DataFrame(image_rows, columns=["filename", "stage", "mask_source", "mask_human_verified", "plant_pixel_fraction_candidate", "plant_sift_features_candidate", "plant_feature_density_per_megapixel_candidate", "foreground_valid_sparse_points_candidate"]).to_csv(destination / "per_image_foreground.csv", index=False)
        global_ids = set().union(*(per_image[image_id] for image_id, pose in poses.items() if labels.get(pose["name"]) == "GLOBAL")) if poses else set()
        local_ids = set().union(*(per_image[image_id] for image_id, pose in poses.items() if broad_label(labels.get(pose["name"])) == "LOCAL")) if poses else set()
        pairs = []
        from itertools import combinations
        for first, second in combinations(sorted(masks), 2):
            name_a, name_b = poses[first]["name"], poses[second]["name"]
            common = sorted(per_image[first] & per_image[second])
            errors = [np.mean([points[point_id]["observation_errors"][first], points[point_id]["observation_errors"][second]]) for point_id in common]
            geometry = pair_statistics(poses[first]["center"], poses[second]["center"], [points[point_id]["xyz"] for point_id in common], errors, minimum=1)
            pairs.append({"filename_i": name_a, "filename_j": name_b, "group": "_".join(sorted([broad_label(labels.get(name_a)), broad_label(labels.get(name_b))])), **covisibility(per_image[first], per_image[second]), **geometry})
        pair_table = pd.DataFrame(pairs, columns=["filename_i", "filename_j", "group", "common_points", "jaccard", "coverage_i_j", "coverage_j_i", "baseline", "median_baseline_depth_ratio", "angle_p10", "angle_median", "angle_p90", "common_3d_points", "reprojection_error", "geometry_valid"])
        pair_table.to_csv(destination / "foreground_pairs.csv", index=False)
        candidate_points = point_table[point_table["class"] == "PLANT_FOREGROUND"]
        def group_angle(group):
            subset = pair_table.loc[pair_table.group == group, "angle_median"].dropna() if len(pair_table) else pd.Series(dtype=float)
            return float(subset.median()) if len(subset) else None
        summary = {"video_id": video_dir.name, "model_path": str(model_path), "mask_images": len(masks), "mask_frames_by_stage": pd.DataFrame(image_rows).groupby("stage").size().to_dict() if image_rows else {}, "human_verified_mask_images": len(verified_images), "candidate_foreground_points": len(foreground_ids), "candidate_track_length_median": float(candidate_points.valid_track_length.median()) if len(candidate_points) else None, "candidate_point_reprojection_error_median": float(candidate_points.point_reprojection_error.median()) if len(candidate_points) else None, "candidate_global_local_pair_angle_median_deg": group_angle("GLOBAL_LOCAL"), "candidate_local_local_pair_angle_median_deg": group_angle("LOCAL_LOCAL"), "human_verified_foreground_points": sum(row["verified_class"] == "PLANT_FOREGROUND" for row in rows), "candidate_global_local_shared": len(global_ids & local_ids), "candidate_local_only": len(local_ids - global_ids), "candidate_background_points": sum(row["class"] == "BACKGROUND" for row in rows), "candidate_uncertain_points": sum(row["class"] == "UNCERTAIN" for row in rows), "verified_plant_geometry_available": len(verified_images) >= 2 and any(row["verified_class"] == "PLANT_FOREGROUND" for row in rows), "status": "PROVISIONAL_AUTO_NOT_TARGET_GROUND_TRUTH" if not verified_images else "HUMAN_VERIFIED_MASKS_PARTIAL", "limitations": ["Masks are 3-valued and must match COLMAP image dimensions and FFmpeg autorotation", "Automatic proposals do not prove plant/pot separation", "Votes are on the same filtered 3D point across multiple images", "No validated same-leaf ROI identity or independent 3D truth"]}
        write_json(destination / "summary.json", summary)
        review_lines = [f"# {video_dir.name} mask review", "", "AUTO PROVISIONAL: none of these masks are human-validated. Validate leaves, thin stems, plant/pot boundary, clutter, blur, occlusion and clipping per frame before changing human_confirmed.", ""]
        review_lines += [f"- {row['filename']} {row['stage']}: {row['mask_source']}; candidate plant pixels {row['plant_pixel_fraction_candidate']:.3f}, plant SIFT {row['plant_sift_features_candidate']}; overlay_{row['filename']}.png" for row in image_rows]
        review_lines.append("\nMissing frames and failures are UNKNOWN, not BACKGROUND. In particular ensure a GLOBAL, APPROACH, LOCAL, blur, occlusion and cropped frame from each video are reviewed separately.\n")
        (destination / "mask_review_checklist.md").write_text("\n".join(review_lines), encoding="utf-8")
        return summary
