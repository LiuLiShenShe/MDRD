from __future__ import annotations

import itertools
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pycolmap

from mdrd.common import read_json, stage, write_json
from mdrd.geometry.core import broad_label, camera_center, covisibility, pair_group, pair_statistics
from mdrd.segmentation import refine_segments
from mdrd.sfm.pipeline import PAIR_ID_FACTOR
from mdrd.visualization.reconstruction import geometry_figures, matching_examples, trajectory_figures


CAMERA_COLUMNS = ["image_id", "filename", "frame_id", "timestamp_sec", "camera_id", "camera_center_x", "camera_center_y", "camera_center_z", "rotation", "translation", "intrinsics", "camera_model", "registered", "segment", "median_observed_depth", "median_ray_distance", "observed_points", "viewing_direction"]
PAIR_COLUMNS = ["image_id_i", "image_id_j", "filename_i", "filename_j", "timestamp_i", "timestamp_j", "segment_i", "segment_j", "group", "time_gap_sec", "baseline", "median_baseline_depth_ratio", "angle_p10", "angle_median", "angle_p90", "common_3d_points", "reprojection_error", "geometry_valid", "common_points", "jaccard", "coverage_i_j", "coverage_j_i", "temporal_block_i", "temporal_block_j", "same_local_segment"]


def read_model_observations(model_path, maximum_error=4, minimum_track=3):
    reconstruction = pycolmap.Reconstruction(model_path)
    poses = {}
    rejected = {"nonfinite_or_high_point_error": 0, "short_track": 0, "invalid_association": 0, "nonpositive_depth": 0, "high_observation_error": 0, "short_after_filter": 0}
    for image_id in reconstruction.reg_image_ids():
        image = reconstruction.images[image_id]
        pose = image.cam_from_world()
        rotation = pose.rotation.matrix()
        translation = pose.translation
        center = camera_center(rotation, translation)
        if not np.allclose(center, image.projection_center(), atol=1e-8):
            raise ValueError("Camera-center convention mismatch")
        poses[image_id] = {"rotation": rotation, "translation": translation, "center": center, "direction": rotation.T @ np.array([0., 0., 1.]), "camera": reconstruction.cameras[image.camera_id], "name": image.name, "camera_id": image.camera_id}
    points = {}
    observations = {image_id: set() for image_id in poses}
    depths = {image_id: [] for image_id in poses}
    distances = {image_id: [] for image_id in poses}
    for point_id, point in reconstruction.points3D.items():
        if not np.all(np.isfinite(point.xyz)) or not np.isfinite(point.error) or point.error > maximum_error:
            rejected["nonfinite_or_high_point_error"] += 1
            continue
        if point.track.length() < minimum_track:
            rejected["short_track"] += 1
            continue
        accepted = []
        for element in point.track.elements:
            image_id = element.image_id
            if image_id not in poses:
                continue
            image = reconstruction.images[image_id]
            if element.point2D_idx >= len(image.points2D) or image.points2D[element.point2D_idx].point3D_id != point_id:
                rejected["invalid_association"] += 1
                continue
            pose = poses[image_id]
            camera_point = pose["rotation"] @ point.xyz + pose["translation"]
            if not np.all(np.isfinite(camera_point)) or camera_point[2] <= 1e-9:
                rejected["nonpositive_depth"] += 1
                continue
            projection = pose["camera"].img_from_cam(camera_point)
            observed = image.points2D[element.point2D_idx].xy
            residual = np.linalg.norm(projection - observed) if projection is not None else np.inf
            if not np.isfinite(residual) or residual > maximum_error:
                rejected["high_observation_error"] += 1
                continue
            accepted.append((image_id, camera_point[2], np.linalg.norm(point.xyz - pose["center"]), residual))
        unique = {item[0]: item for item in accepted}
        if len(unique) < minimum_track:
            rejected["short_after_filter"] += 1
            continue
        points[point_id] = {"xyz": point.xyz, "error": point.error, "images": set(unique), "track_length": len(unique), "color": point.color, "observation_errors": {item[0]: item[3] for item in unique.values()}}
        for image_id, depth, distance, _ in unique.values():
            observations[image_id].add(point_id)
            depths[image_id].append(depth)
            distances[image_id].append(distance)
    return reconstruction, poses, points, observations, depths, distances, rejected


def camera_table(manifest, coarse, database_images, poses, observations, depths, distances):
    labels = coarse.set_index("filename").label.to_dict()
    by_name = {pose["name"]: image_id for image_id, pose in poses.items()}
    database = database_images.set_index("name").to_dict("index")
    records = []
    for item in manifest.to_dict("records"):
        filename = item["filename"]
        image_id = by_name.get(filename)
        pose = poses.get(image_id)
        db_image = database.get(filename, {})
        registered = pose is not None
        center = pose["center"] if registered else [np.nan] * 3
        camera = pose["camera"] if registered else None
        records.append({"image_id": image_id if registered else db_image.get("image_id", np.nan), "filename": filename, "frame_id": item["frame_id"], "timestamp_sec": item["timestamp_sec"], "camera_id": pose["camera_id"] if registered else db_image.get("camera_id", np.nan), "camera_center_x": center[0], "camera_center_y": center[1], "camera_center_z": center[2], "rotation": json.dumps(pose["rotation"].tolist()) if registered else None, "translation": json.dumps(pose["translation"].tolist()) if registered else None, "intrinsics": json.dumps(camera.params.tolist()) if camera is not None else None, "camera_model": camera.model_name if camera is not None else None, "registered": registered, "segment": labels.get(filename, "UNKNOWN"), "median_observed_depth": np.median(depths[image_id]) if registered and depths[image_id] else np.nan, "median_ray_distance": np.median(distances[image_id]) if registered and distances[image_id] else np.nan, "observed_points": len(observations[image_id]) if registered else 0, "viewing_direction": json.dumps(pose["direction"].tolist()) if registered else None})
    return pd.DataFrame(records, columns=CAMERA_COLUMNS)


def pairwise_analysis(cameras, poses, points, observations, parameters):
    rows = []
    all_rows = cameras.to_dict("records")
    number = len(all_rows)
    common_counts = np.full((number, number), np.nan)
    jaccard = np.full((number, number), np.nan)
    directional = np.full((number, number), np.nan)
    for first_index, first in enumerate(all_rows):
        first_id = first["image_id"]
        first_points = observations.get(first_id) if first["registered"] else None
        for second_index in range(first_index, number):
            second = all_rows[second_index]
            second_id = second["image_id"]
            second_points = observations.get(second_id) if second["registered"] else None
            statistics = covisibility(first_points, second_points)
            common_counts[first_index, second_index] = common_counts[second_index, first_index] = statistics["common_points"]
            jaccard[first_index, second_index] = jaccard[second_index, first_index] = statistics["jaccard"]
            directional[first_index, second_index] = statistics["coverage_i_j"]
            directional[second_index, first_index] = statistics["coverage_j_i"]
            if first_index == second_index:
                continue
            geometric = {"baseline": np.nan, "median_baseline_depth_ratio": np.nan, "angle_p10": np.nan, "angle_median": np.nan, "angle_p90": np.nan, "common_3d_points": np.nan, "reprojection_error": np.nan, "geometry_valid": False}
            if first_points is not None and second_points is not None:
                common = sorted(first_points & second_points)
                xyz = np.array([points[point_id]["xyz"] for point_id in common]).reshape(-1, 3)
                errors = [np.mean([points[point_id]["observation_errors"][first_id], points[point_id]["observation_errors"][second_id]]) for point_id in common]
                geometric = pair_statistics(poses[first_id]["center"], poses[second_id]["center"], xyz, errors, parameters["min_common_points"])
            rows.append({"image_id_i": first_id, "image_id_j": second_id, "filename_i": first["filename"], "filename_j": second["filename"], "timestamp_i": first["timestamp_sec"], "timestamp_j": second["timestamp_sec"], "segment_i": first["segment"], "segment_j": second["segment"], "group": pair_group(first["segment"], second["segment"]), "time_gap_sec": second["timestamp_sec"] - first["timestamp_sec"], **geometric, **statistics, "temporal_block_i": int(first["timestamp_sec"] // parameters["temporal_block_sec"]), "temporal_block_j": int(second["timestamp_sec"] // parameters["temporal_block_sec"]), "same_local_segment": str(first["segment"]).startswith("LOCAL_") and first["segment"] == second["segment"]})
    return pd.DataFrame(rows, columns=PAIR_COLUMNS), common_counts, jaccard, directional


def group_statistics(pairs):
    rows = []
    blocks = []
    metrics = ["median_baseline_depth_ratio", "angle_median", "common_3d_points", "jaccard", "coverage_i_j", "coverage_j_i", "reprojection_error"]
    for group in ["GLOBAL_GLOBAL", "LOCAL_LOCAL", "GLOBAL_LOCAL", "GLOBAL_APPROACH", "APPROACH_LOCAL", "OTHER"]:
        subset = pairs[pairs.group == group]
        valid = subset[subset.geometry_valid]
        record = {"group": group, "all_pairs": len(subset), "registered_pairs": int(subset.common_points.notna().sum()), "valid_pairs": len(valid)}
        block_rows = []
        for (first, second), block in valid.groupby(["temporal_block_i", "temporal_block_j"]):
            block_record = {"group": group, "temporal_block_i": first, "temporal_block_j": second, "pairs_in_block": len(block)}
            block_record.update({metric: block[metric].median() for metric in metrics})
            block_rows.append(block_record)
        record["temporal_block_pairs"] = len(block_rows)
        for metric in metrics:
            record[metric] = valid[metric].median() if len(valid) else np.nan
            record[f"block_median_{metric}"] = np.median([item[metric] for item in block_rows]) if block_rows else np.nan
        rows.append(record)
        blocks += block_rows
    return pd.DataFrame(rows), pd.DataFrame(blocks, columns=["group", "temporal_block_i", "temporal_block_j", "pairs_in_block"] + metrics)


def track_statistics(points, cameras, poses):
    labels = cameras.set_index("image_id").segment.to_dict()
    rows = []
    for point_id, point in points.items():
        image_ids = sorted(point["images"])
        centers = [poses[image_id]["center"] for image_id in image_ids]
        rays = np.array([point["xyz"] - center for center in centers])
        rays /= np.linalg.norm(rays, axis=1)[:, None]
        cosines = np.clip(rays @ rays.T, -1, 1)
        max_angle = np.degrees(np.arccos(np.min(cosines)))
        directions = []
        for ray in rays:
            if not directions or max(float(ray @ item) for item in directions) < np.cos(np.radians(5)):
                directions.append(ray)
        counts = {label: sum(broad_label(labels.get(image_id, "UNKNOWN")) == label for image_id in point["images"]) for label in ["GLOBAL", "LOCAL", "APPROACH"]}
        group_angles = {}
        for first_label, second_label in [("GLOBAL", "GLOBAL"), ("LOCAL", "LOCAL"), ("GLOBAL", "LOCAL")]:
            angles = [np.degrees(np.arccos(cosines[first, second])) for first in range(len(image_ids)) for second in range(first + 1, len(image_ids)) if pair_group(labels.get(image_ids[first], "UNKNOWN"), labels.get(image_ids[second], "UNKNOWN")) == f"{first_label}_{second_label}"]
            group_angles[f"{first_label.lower()}_{second_label.lower()}_max_angle_deg"] = max(angles) if angles else np.nan
        global_rays = rays[[broad_label(labels.get(image_id)) == "GLOBAL" for image_id in image_ids]]
        local_rays = rays[[broad_label(labels.get(image_id)) == "LOCAL" for image_id in image_ids]]
        new_directions = np.degrees(np.arccos(np.clip(np.max(local_rays @ global_rays.T, axis=1), -1, 1))) if len(global_rays) and len(local_rays) else []
        rows.append({"point3d_id": point_id, "track_length": point["track_length"], "global_observations": counts["GLOBAL"], "local_observations": counts["LOCAL"], "approach_observations": counts["APPROACH"], "max_ray_angle_deg": max_angle, "greedy_direction_bins_5deg": len(directions), "reprojection_error": point["error"], "global_local_shared": counts["GLOBAL"] > 0 and counts["LOCAL"] > 0, "local_without_global": counts["LOCAL"] > 0 and counts["GLOBAL"] == 0, "max_local_nearest_global_angle_deg": max(new_directions) if len(new_directions) else np.nan, **group_angles})
    return pd.DataFrame(rows, columns=["point3d_id", "track_length", "global_observations", "local_observations", "approach_observations", "max_ray_angle_deg", "greedy_direction_bins_5deg", "reprojection_error", "global_local_shared", "local_without_global", "global_global_max_angle_deg", "local_local_max_angle_deg", "global_local_max_angle_deg", "max_local_nearest_global_angle_deg"])


def temporal_sensitivity(pairs):
    bins = [(0, 1, "0_to_1s"), (1, 3, "1_to_3s"), (3, 10, "3_to_10s"), (10, np.inf, "above_10s")]
    rows = []
    for group in ["GLOBAL_GLOBAL", "LOCAL_LOCAL", "GLOBAL_LOCAL"]:
        for lower, upper, label in bins:
            for within_segment in [False, True]:
                subset = pairs[(pairs.group == group) & (pairs.time_gap_sec > lower) & (pairs.time_gap_sec <= upper)]
                if within_segment:
                    subset = subset[subset.segment_i == subset.segment_j]
                valid = subset[subset.geometry_valid]
                rows.append({"group": group, "time_gap_bin": label, "same_segment_only": within_segment, "total_pairs": len(subset), "registered_pairs": int(subset.common_points.notna().sum()), "valid_pairs": len(valid), "angle_median": valid.angle_median.median(), "jaccard_median": valid.jaccard.median(), "baseline_depth_ratio_median": valid.median_baseline_depth_ratio.median(), "temporal_block_pairs": valid.groupby(["temporal_block_i", "temporal_block_j"]).ngroups})
    return pd.DataFrame(rows)


def matching_statistics(directory, cameras):
    database_pairs = pd.read_csv(Path(directory) / "sfm" / "database_pairs.csv")
    labels = cameras.set_index("filename").segment.to_dict()
    database_pairs["segment_i"] = database_pairs.filename_i.map(labels)
    database_pairs["segment_j"] = database_pairs.filename_j.map(labels)
    database_pairs["group"] = [pair_group(first, second) for first, second in zip(database_pairs.segment_i, database_pairs.segment_j)]
    database_pairs["geometry_verified_15"] = database_pairs.verified_match_count >= 15
    database_pairs["local_global_scale_ratio"] = np.nan
    with sqlite3.connect(Path(directory) / "sfm" / "database.db") as connection:
        keypoints = {image_id: np.frombuffer(data, dtype=np.float32).reshape(rows, columns) for image_id, rows, columns, data in connection.execute("SELECT image_id,rows,cols,data FROM keypoints") if rows}
        for index, item in database_pairs[database_pairs.group == "GLOBAL_LOCAL"].iterrows():
            first = int(item.image_id_i)
            second = int(item.image_id_j)
            pair_id = min(first, second) * PAIR_ID_FACTOR + max(first, second)
            result = connection.execute("SELECT rows,cols,data FROM two_view_geometries WHERE pair_id=?", (pair_id,)).fetchone()
            if result is None or result[0] < 15 or first not in keypoints or second not in keypoints:
                continue
            matches = np.frombuffer(result[2], dtype=np.uint32).reshape(result[0], result[1])
            sizes = []
            for image_id in [first, second]:
                array = keypoints[image_id]
                size = np.sqrt(np.abs(array[:, 2] * array[:, 5] - array[:, 3] * array[:, 4])) if array.shape[1] == 6 else array[:, 2]
                sizes.append(size)
            scale = sizes[1][matches[:, 1]] / np.maximum(sizes[0][matches[:, 0]], 1e-9)
            if broad_label(item.segment_i) == "LOCAL":
                scale = 1 / np.maximum(scale, 1e-9)
            database_pairs.loc[index, "local_global_scale_ratio"] = np.median(scale[np.isfinite(scale)])
    summaries = []
    for group, subset in database_pairs.groupby("group"):
        summaries.append({"group": group, "tested_pairs_in_database": len(subset), "geometry_verified_pairs_15": int(subset.geometry_verified_15.sum()), "verification_rate": subset.geometry_verified_15.mean(), "raw_matches_median": subset.match_count.median(), "verified_matches_median": subset.verified_match_count.median(), "local_global_scale_ratio_median": subset.local_global_scale_ratio.median()})
    database_pairs.to_csv(Path(directory) / "geometry" / "matching_pairs.csv", index=False)
    summary = pd.DataFrame(summaries)
    summary.to_csv(Path(directory) / "geometry" / "matching_group_comparison.csv", index=False)
    return database_pairs, summary


def registration_audit(directory, cameras, quality, matching):
    database_images = pd.read_csv(Path(directory) / "sfm" / "database_images.csv")
    audit = cameras.merge(database_images[["name", "sift_features"]], left_on="filename", right_on="name", how="left").merge(quality[["filename", "quality_label", "laplacian_variance", "relative_laplacian", "feature_match_count"]], on="filename", how="left")
    raw_counts = {}
    verified_counts = {}
    global_connections = {}
    for item in matching.to_dict("records"):
        for name in [item["filename_i"], item["filename_j"]]:
            raw_counts[name] = max(raw_counts.get(name, 0), item["match_count"] if np.isfinite(item["match_count"]) else 0)
            verified_counts[name] = max(verified_counts.get(name, 0), item["verified_match_count"])
            if item["group"] == "GLOBAL_LOCAL":
                global_connections[name] = max(global_connections.get(name, 0), item["verified_match_count"])
    audit["match_count"] = audit.filename.map(raw_counts)
    audit["verified_match_count"] = audit.filename.map(verified_counts)
    audit["max_global_local_verified_matches"] = audit.filename.map(global_connections)
    audit["pnp_inliers"] = np.nan
    audit["registration_status"] = np.where(audit.registered, "REGISTERED", "UNREGISTERED")
    audit["failure_reason"] = np.where(audit.registered, "N/A", "UNKNOWN")
    audit.loc[~audit.registered & (audit.sift_features < 30), "failure_reason"] = "LOW_FEATURE_COUNT"
    audit["segment_id"] = audit.segment
    audit.to_csv(Path(directory) / "sfm" / "registration_audit.csv", index=False)
    rows = []
    for segment, subset in audit.groupby("segment"):
        rows.append({"segment": segment, "total": len(subset), "registered": int(subset.registered.sum()), "registration_rate": subset.registered.mean()})
    pd.DataFrame(rows).to_csv(Path(directory) / "sfm" / "registration_by_segment.csv", index=False)
    comparisons = []
    for (segment, label), subset in audit.groupby(["segment", "quality_label"]):
        comparisons.append({"segment": segment, "quality_label": label, "frames": len(subset), "registered": int(subset.registered.sum()), "registration_rate": subset.registered.mean(), "sift_features_median": subset.sift_features.median(), "verified_matches_median": subset.verified_match_count.median(), "relative_laplacian_median": subset.relative_laplacian.median()})
    pd.DataFrame(comparisons).to_csv(Path(directory) / "geometry" / "blur_registration_comparison.csv", index=False)
    return audit


def motion_table(cameras, poses):
    rows = []
    previous = None
    for item in cameras.to_dict("records"):
        record = {"filename": item["filename"], "timestamp_sec": item["timestamp_sec"], "registered": item["registered"], "translation_relative_units": np.nan, "rotation_deg": np.nan, "direction_x": np.nan, "direction_y": np.nan, "direction_z": np.nan, "time_gap_sec": np.nan, "consecutive_source_sample": False}
        if item["registered"]:
            current = poses[item["image_id"]]
            if previous is not None:
                previous_item, previous_pose = previous
                difference = current["center"] - previous_pose["center"]
                baseline = np.linalg.norm(difference)
                rotation = current["rotation"] @ previous_pose["rotation"].T
                angle = np.degrees(np.arccos(np.clip((np.trace(rotation) - 1) / 2, -1, 1)))
                direction = difference / baseline if baseline > 1e-12 else [np.nan] * 3
                record.update(translation_relative_units=baseline, rotation_deg=angle, direction_x=direction[0], direction_y=direction[1], direction_z=direction[2], time_gap_sec=item["timestamp_sec"] - previous_item["timestamp_sec"], consecutive_source_sample=item["frame_id"] == previous_item["frame_id"] + 1)
            previous = item, current
        rows.append(record)
    return pd.DataFrame(rows)


def analyze(directory, configuration, force=False):
    directory = Path(directory)
    output = directory / "geometry"
    output.mkdir(exist_ok=True)
    summary_path = directory / "sfm" / "sfm_summary.json"
    parameters = configuration["geometry"]
    sfm = read_json(summary_path)
    input_paths = [summary_path, directory / "frame_manifest.csv", directory / "quality" / "frame_quality.csv", directory / "segments" / "coarse_frame_labels.csv"]
    if sfm.get("model_path"):
        input_paths += list(Path(sfm["model_path"]).glob("*.bin"))
    with stage(directory, "analyze", parameters, input_paths, force) as execute:
        if not execute:
            return read_json(output / "diagnosis.json")
        manifest = pd.read_csv(directory / "frame_manifest.csv")
        coarse = pd.read_csv(directory / "segments" / "coarse_frame_labels.csv")
        quality = pd.read_csv(directory / "quality" / "frame_quality.csv")
        database_images = pd.read_csv(directory / "sfm" / "database_images.csv")
        if sfm.get("model_path"):
            reconstruction, poses, points, observations, depths, distances, rejected = read_model_observations(sfm["model_path"], parameters["max_reprojection_error"], parameters["min_track_length"])
        else:
            reconstruction = None
            poses, points, observations, depths, distances, rejected = {}, {}, {}, {}, {}, {}
        cameras = camera_table(manifest, coarse, database_images, poses, observations, depths, distances)
        global_ids = set(cameras.loc[cameras.registered & cameras.segment.eq("GLOBAL"), "image_id"])
        shared_reference = {}
        for point_id, point in points.items():
            reference_centers = [poses[image_id]["center"] for image_id in point["images"] & global_ids]
            if len(reference_centers) >= 2:
                shared_reference[point_id] = np.median([np.linalg.norm(point["xyz"] - center) for center in reference_centers])
        shared_ratios, adjacent_coverage = [], []
        previous_points = None
        for item in cameras.to_dict("records"):
            image_id = item["image_id"]
            observed = observations.get(image_id) if item["registered"] else None
            if observed is not None:
                ratios = [np.linalg.norm(points[point_id]["xyz"] - poses[image_id]["center"]) / shared_reference[point_id] for point_id in observed & shared_reference.keys() if shared_reference[point_id] > 1e-9]
                shared_ratios.append(np.median(ratios) if len(ratios) >= 30 else np.nan)
            else:
                shared_ratios.append(np.nan)
            adjacent_coverage.append(covisibility(previous_points, observed)["jaccard"])
            previous_points = observed
        cameras["median_shared_global_distance_ratio"] = shared_ratios
        cameras["adjacent_sparse_jaccard"] = adjacent_coverage
        refined = refine_segments(directory, cameras, configuration)
        cameras["segment"] = refined.label.to_numpy()
        cameras["segment_confidence"] = refined.confidence.to_numpy()
        cameras["geometry_validated_label"] = refined.geometry_validated.to_numpy()
        cameras.to_csv(output / "cameras.csv", index=False)
        motions = motion_table(cameras, poses)
        motions.to_csv(output / "camera_motion.csv", index=False)
        pairs, common, jaccard, directional = pairwise_analysis(cameras, poses, points, observations, parameters)
        pairs.to_csv(output / "pairwise_geometry.csv", index=False)
        groups, blocks = group_statistics(pairs)
        groups.to_csv(output / "geometry_group_comparison.csv", index=False)
        blocks.to_csv(output / "geometry_temporal_block_comparison.csv", index=False)
        temporal_sensitivity(pairs).to_csv(output / "geometry_temporal_gap_sensitivity.csv", index=False)
        local_within = pairs[(pairs.group == "LOCAL_LOCAL") & pairs.same_local_segment & (pairs.time_gap_sec <= 3)]
        _, within_blocks = group_statistics(local_within)
        within_blocks.to_csv(output / "local_within_segment_short_gap_blocks.csv", index=False)
        np.save(output / "common_counts.npy", common)
        np.save(output / "covisibility.npy", jaccard)
        np.save(output / "directional_coverage.npy", directional)
        write_json(output / "covisibility_index.json", {"ordered_filenames": cameras.filename.tolist(), "registered": cameras.registered.tolist(), "point_filter": parameters, "note": "NaN for unregistered or empty denominators. Sparse successfully reconstructed feature visibility, not plant surface visibility."})
        tracks = track_statistics(points, cameras, poses)
        tracks.to_csv(output / "point_track_geometry.csv", index=False)
        matching, match_summary = matching_statistics(directory, cameras)
        audit = registration_audit(directory, cameras, quality, matching)
        trajectory_figures(directory, cameras, motions, points)
        geometry_figures(directory, cameras, pairs, groups, common, jaccard)
        matching_examples(directory, audit, matching)
        from mdrd.reporting.hypotheses import diagnose
        diagnosis = diagnose(directory.name, cameras, groups, blocks, tracks, match_summary, audit, parameters)
        diagnosis["hypotheses"]["H2"]["evidence"]["within_same_local_segment_gap_le_3s_valid_pairs"] = int(local_within.geometry_valid.sum())
        diagnosis["hypotheses"]["H2"]["evidence"]["within_segment_short_gap_blocks"] = len(within_blocks)
        short_fraction = ((within_blocks.jaccard >= parameters["high_covisibility"]) & (within_blocks.angle_median < parameters["low_angle_deg"])).mean()
        diagnosis["hypotheses"]["H2"]["evidence"]["within_segment_short_gap_high_jaccard_low_angle_fraction"] = short_fraction
        if len(within_blocks) < parameters["min_independent_blocks"]:
            diagnosis["hypotheses"]["H2"]["status"] = "INCONCLUSIVE"
        elif short_fraction >= .5:
            diagnosis["hypotheses"]["H2"]["status"] = "SUPPORTED"
        elif short_fraction <= .1:
            diagnosis["hypotheses"]["H2"]["status"] = "NOT_SUPPORTED"
        else:
            diagnosis["hypotheses"]["H2"]["status"] = "INCONCLUSIVE"
        diagnosis["hypotheses"]["H2"]["basis"] += " Primary H2 decision uses same-local-segment pairs at <=3 s lag. COLMAP min triangulation angle and successful-registration selection censor unreconstructed/weak observations; NOT_SUPPORTED applies only to recovered-feature evidence."
        diagnosis["hypotheses"]["H3"]["evidence"]["shared_points_with_local_direction_over_5deg_from_nearest_global"] = int((tracks.max_local_nearest_global_angle_deg > 5).sum())
        diagnosis.update({"filter_rejections": rejected, "raw_3d_points": reconstruction.num_points3D() if reconstruction is not None else 0, "valid_3d_points": len(points), "registered_images": int(cameras.registered.sum()), "total_images": len(cameras), "trajectory_max_rotation_deg": motions.rotation_deg.max(), "trajectory_step_p99_over_median": motions.translation_relative_units.quantile(.99) / motions.translation_relative_units.median() if motions.translation_relative_units.median() > 0 else None, "model_strategy": sfm.get("strategy"), "limitations": ["No plant foreground masks; all geometric conclusions concern recovered full-scene features.", "No metric scale or known gravity; absolute baselines cannot be pooled across videos.", "Segment labels are proxy evidence, with unregistered temporal inference explicitly marked.", "Pair and time-block statistics remain correlated; no independent-pair significance test or causal blur claim.", "8-bit sharpness/exposure diagnostics of HDR source are not calibrated radiometry."]})
        write_json(output / "diagnosis.json", diagnosis)
        proposal = adaptive_proposal(manifest, quality, refined, audit)
        write_json(output / "adaptive_supplement_proposal.json", proposal)
        print(f"ANALYZE {directory.name} {len(points)} valid points {int(pairs.geometry_valid.sum())} valid pairs", flush=True)
        return diagnosis


def adaptive_proposal(manifest, quality, refined, audit, maximum=12):
    candidates = []
    motion_cutoff = quality.frame_motion_median.quantile(.85)
    for index in range(1, len(manifest)):
        first, second = manifest.iloc[index - 1], manifest.iloc[index]
        reasons = []
        if quality.iloc[index].frame_motion_median >= motion_cutoff:
            reasons.append("HIGH_2D_MOTION_NOT_METRIC_TRANSLATION")
        if refined.iloc[index].label != refined.iloc[index - 1].label:
            reasons.append("SEGMENT_BOUNDARY")
        if not audit.iloc[index].registered or not audit.iloc[index - 1].registered:
            reasons.append("REGISTRATION_GAP")
        if quality.iloc[index].verified_match_count < 15:
            reasons.append("LOW_ADJACENT_HOMOGRAPHY_SUPPORT")
        if reasons:
            candidates.append({"timestamp_sec": (first.timestamp_sec + second.timestamp_sec) / 2, "reasons": reasons, "priority": len(reasons) + int("REGISTRATION_GAP" in reasons)})
    selected = sorted(candidates, key=lambda item: (-item["priority"], item["timestamp_sec"]))[:maximum]
    return {"timestamps": sorted(item["timestamp_sec"] for item in selected), "candidates": selected, "maximum_additional_frames": maximum, "policy": "Preserve existing selected decoded frame indices; add nearest actual source PTS. Proposal is not a claim that new frames will register."}
