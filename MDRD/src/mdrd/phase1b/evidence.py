from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pycolmap

from mdrd.common import read_json, write_json
from mdrd.geometry.analysis import read_model_observations
from mdrd.geometry.core import broad_label, triangulation_angles
from mdrd.sfm.pipeline import PAIR_ID_FACTOR


def fit_sim3(source, target):
    first = np.asarray(source, dtype=float)
    second = np.asarray(target, dtype=float)
    if first.shape != second.shape or first.ndim != 2 or first.shape[1] != 3 or len(first) < 3 or not np.isfinite(first).all() or not np.isfinite(second).all():
        raise ValueError("Sim(3) requires at least three finite corresponding 3D centers")
    center_a, center_b = first.mean(0), second.mean(0)
    shifted_a, shifted_b = first - center_a, second - center_b
    if np.linalg.matrix_rank(shifted_a) < 2:
        raise ValueError("Degenerate Sim(3) camera centers")
    left, singular, right = np.linalg.svd(shifted_b.T @ shifted_a)
    flip = np.diag([1., 1., np.linalg.det(left @ right)])
    rotation = left @ flip @ right
    scale = float(np.trace(np.diag(singular) @ flip) / np.sum(shifted_a ** 2))
    if scale <= 0:
        raise ValueError("Invalid Sim(3) scale")
    translation = center_b - scale * rotation @ center_a
    residuals = np.linalg.norm((scale * (rotation @ first.T)).T + translation - second, axis=1)
    return {"scale": scale, "rotation": rotation, "translation": translation, "rms_residual": float(np.sqrt(np.mean(residuals ** 2))), "max_residual": float(np.max(residuals)), "common_images": len(first)}


def align_models(source_path, target_path):
    source, target = pycolmap.Reconstruction(source_path), pycolmap.Reconstruction(target_path)
    source_centers = {source.images[image_id].name: source.images[image_id].projection_center() for image_id in source.reg_image_ids()}
    target_centers = {target.images[image_id].name: target.images[image_id].projection_center() for image_id in target.reg_image_ids()}
    shared = sorted(source_centers.keys() & target_centers.keys())
    if len(shared) < 3:
        return {"status": "N/A", "reason": "Fewer than three common registered cameras", "common_images": len(shared)}
    try:
        transform = fit_sim3([source_centers[name] for name in shared], [target_centers[name] for name in shared])
    except ValueError as exception:
        return {"status": "N/A", "reason": str(exception), "common_images": len(shared)}
    span = float(np.sqrt(np.mean(np.sum((np.array([target_centers[name] for name in shared]) - np.mean([target_centers[name] for name in shared], axis=0)) ** 2, axis=1))))
    return {"status": "ALIGNED_COMMON_CAMERAS_ONLY", "common_images": len(shared), "scale": transform["scale"], "rms_residual": transform["rms_residual"], "normalized_rms_residual": transform["rms_residual"] / span if span > 0 else None, "max_residual": transform["max_residual"], "caution": "Camera alignment does not imply 3D points are corresponding or have ground-truth accuracy"}


def distinct_new_directions(point, global_centers, local_centers):
    xyz = np.asarray(point, dtype=float)
    if not global_centers or not local_centers:
        return []
    return [float(np.nanmin(triangulation_angles(local, global_centers[0], [xyz]))) if len(global_centers) == 1 else float(np.nanmin([triangulation_angles(local, center, [xyz])[0] for center in global_centers])) for local in local_centers]


def point_information(point, observations, effective_gap_sec=0):
    if not observations:
        return None
    matrices = {}
    for label, subset in (("GLOBAL_ONLY", [row for row in observations if row["stage"] == "GLOBAL"]), ("GLOBAL_LOCAL", [row for row in observations if row["stage"] in {"GLOBAL", "LOCAL"}]), ("GLOBAL_APPROACH_LOCAL", observations)):
        previous = -np.inf
        information = np.zeros((3, 3), dtype=float)
        for row in sorted(subset, key=lambda item: item["time"]):
            if row["time"] - previous < effective_gap_sec:
                continue
            jacobian = np.asarray(row["jacobian"], dtype=float)
            if jacobian.shape != (2, 3) or not np.isfinite(jacobian).all():
                continue
            information += jacobian.T @ jacobian
            previous = row["time"]
        eigenvalues = np.linalg.eigvalsh(information)
        matrices[label] = {"smallest": float(eigenvalues[0]), "largest": float(eigenvalues[-1]), "condition": float(eigenvalues[-1] / eigenvalues[0]) if eigenvalues[0] > 1e-12 else None, "rank": int(np.linalg.matrix_rank(information, tol=1e-12))}
    return matrices


def matching_funnel(database, reconstruction, filenames):
    selected = set(filenames)
    with sqlite3.connect(database) as connection:
        ids = {image_id: name for image_id, name in connection.execute("SELECT image_id,name FROM images")}
        raw = dict(connection.execute("SELECT pair_id,rows FROM matches"))
        verified = dict(connection.execute("SELECT pair_id,rows FROM two_view_geometries"))
    selected_ids = [image_id for image_id, name in ids.items() if name in selected]
    reconstructed = {reconstruction.images[image_id].name: reconstruction.images[image_id] for image_id in reconstruction.reg_image_ids()}
    from itertools import combinations
    rows = []
    for first, second in combinations(sorted(selected_ids), 2):
        pair_id = PAIR_ID_FACTOR * first + second
        name_a, name_b = ids[first], ids[second]
        points_a = {p.point3D_id for p in reconstructed[name_a].points2D if p.has_point3D()} if name_a in reconstructed else set()
        points_b = {p.point3D_id for p in reconstructed[name_b].points2D if p.has_point3D()} if name_b in reconstructed else set()
        rows.append({"filename_i": name_a, "filename_j": name_b, "candidate": True, "raw_matches": int(raw.get(pair_id, 0)), "verified_matches": int(verified.get(pair_id, 0)), "common_tracks": len(points_a & points_b), "both_registered": name_a in reconstructed and name_b in reconstructed})
    return pd.DataFrame(rows, columns=["filename_i", "filename_j", "candidate", "raw_matches", "verified_matches", "common_tracks", "both_registered"])


def analyze_evidence(video_dir, destination, model_path=None):
    video_dir, destination = Path(video_dir), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    model_path = model_path or read_json(video_dir / "sfm" / "sfm_summary.json")["model_path"]
    reconstruction, poses, points, _, _, _, rejected = read_model_observations(model_path)
    labels_file = video_dir / "segments" / "segment_confidence.csv"
    if not labels_file.exists():
        labels_file = video_dir / "segments" / "coarse_frame_labels.csv"
    labels = pd.read_csv(labels_file).set_index("filename").label.to_dict()
    manifest = pd.read_csv(video_dir / "frame_manifest.csv").set_index("filename").timestamp_sec.to_dict()
    rows = []
    for point_id, point in points.items():
        grouped = {stage: [image_id for image_id in point["images"] if broad_label(labels.get(poses[image_id]["name"])) == stage] for stage in ("GLOBAL", "APPROACH", "LOCAL")}
        if not grouped["GLOBAL"] or not grouped["LOCAL"]:
            continue
        new_angles = distinct_new_directions(point["xyz"], [poses[image_id]["center"] for image_id in grouped["GLOBAL"]], [poses[image_id]["center"] for image_id in grouped["LOCAL"]])
        rows.append({"point3d_id": point_id, "global_observations": len(grouped["GLOBAL"]), "local_observations": len(grouped["LOCAL"]), "approach_observations": len(grouped["APPROACH"]), "max_local_new_direction_deg": max(new_angles), "max_global_angle_deg": float(np.nanmax([triangulation_angles(poses[a]["center"], poses[b]["center"], [point["xyz"]])[0] for a, b in __import__('itertools').combinations(grouped["GLOBAL"], 2)])) if len(grouped["GLOBAL"]) >= 2 else None, "point_reprojection_error": point["error"]})
    tracks = pd.DataFrame(rows, columns=["point3d_id", "global_observations", "local_observations", "approach_observations", "max_local_new_direction_deg", "max_global_angle_deg", "point_reprojection_error"])
    tracks.to_csv(destination / "same_point_direction_gain.csv", index=False)
    frames = pd.read_csv(video_dir / "frame_manifest.csv")
    funnel = matching_funnel(video_dir / "sfm" / "database.db", reconstruction, frames.filename)
    funnel.to_csv(destination / "match_to_track_funnel.csv", index=False)
    raw_pairs = int((funnel.raw_matches > 0).sum())
    verified_pairs = int((funnel.verified_matches > 0).sum())
    summary = {"video_id": video_dir.name, "model": str(model_path), "scope": "FULL_SCENE_FILTERED_SAME_RECONSTRUCTION_POINTS; NOT_PLANT_GEOMETRY", "same_points_global_and_local": len(tracks), "median_new_local_direction_deg": float(tracks.max_local_new_direction_deg.median()) if len(tracks) else None, "local_direction_p10_deg": float(tracks.max_local_new_direction_deg.quantile(.1)) if len(tracks) else None, "local_direction_p90_deg": float(tracks.max_local_new_direction_deg.quantile(.9)) if len(tracks) else None, "local_directions_over_5deg": int((tracks.max_local_new_direction_deg > 5).sum()) if len(tracks) else 0, "candidate_pairs": len(funnel), "pairs_with_raw_matches": raw_pairs, "pairs_with_verified_matches": verified_pairs, "pairs_with_common_tracks": int((funnel.common_tracks > 0).sum()), "pairs_with_verified_but_no_shared_3d_track": int(((funnel.verified_matches > 0) & (funnel.common_tracks == 0)).sum()), "candidate_to_raw_pair_retention": raw_pairs / len(funnel) if len(funnel) else None, "raw_to_verified_pair_retention": verified_pairs / raw_pairs if raw_pairs else None, "raw_matches_total": int(funnel.raw_matches.sum()), "verified_matches_total": int(funnel.verified_matches.sum()), "filter_rejections": rejected, "plant_pair_match_funnel": None, "limitations": ["Pair retention refers to pairs with at least one match, not retention of identical point correspondences", "Two-view geometrically verified pairs and 3D track overlap are not nested sets", "Only successfully reconstructed tracks have direction gain", "No cross-model point IDs are equated without independently verified correspondences"]}
    write_json(destination / "summary.json", summary)
    return summary
