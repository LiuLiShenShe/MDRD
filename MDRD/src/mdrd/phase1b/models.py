from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pycolmap

from mdrd.common import sha256, write_json
from mdrd.geometry.analysis import read_model_observations
from mdrd.geometry.core import broad_label


def candidate_paths(root):
    root = Path(root)
    return sorted(path.parent for path in root.rglob("images.bin") if path.parent != root and all((path.parent / f"{name}.bin").is_file() for name in ("cameras", "images", "points3D")))


def summarize_candidate(path, labels):
    reconstruction = pycolmap.Reconstruction(path)
    registered = [reconstruction.images[image_id] for image_id in reconstruction.reg_image_ids()]
    present = {image.name for image in registered}
    coverage = {}
    for label, subset in labels.groupby(labels.label.map(broad_label)):
        names = set(subset.filename)
        coverage[str(label)] = {"registered": len(names & present), "total": len(names), "fraction": len(names & present) / len(names) if names else None}
    errors = np.array([point.error for point in reconstruction.points3D.values() if np.isfinite(point.error)])
    tracks = np.array([point.track.length() for point in reconstruction.points3D.values()], dtype=int)
    cameras = list(reconstruction.cameras.values())
    local_names = set(labels.loc[labels.label.astype(str).str.startswith("LOCAL"), "filename"])
    global_names = set(labels.loc[labels.label == "GLOBAL", "filename"])
    bridge_count = 0
    bridged_local = set()
    for point in reconstruction.points3D.values():
        names = {reconstruction.images[element.image_id].name for element in point.track.elements if element.image_id in reconstruction.images}
        bridge_count += bool(names & local_names and names & global_names)
        if names & global_names:
            bridged_local |= names & local_names
    timestamps = labels.set_index("filename").timestamp_sec.to_dict() if "timestamp_sec" in labels else {}
    ordered = sorted(registered, key=lambda image: timestamps.get(image.name, 0))
    steps = [np.linalg.norm(second.projection_center() - first.projection_center()) for first, second in zip(ordered[:-1], ordered[1:])]
    rotations = [np.degrees(np.arccos(np.clip((np.trace(second.cam_from_world().rotation.matrix() @ first.cam_from_world().rotation.matrix().T) - 1) / 2, -1, 1))) for first, second in zip(ordered[:-1], ordered[1:])]
    _, _, valid_points, _, _, _, rejections = read_model_observations(path)
    names = ("cameras", "images", "points3D")
    return {"path": str(Path(path).resolve()), "registered_images": len(registered), "registered_filenames": sorted(present), "coverage": coverage, "points3d_raw": reconstruction.num_points3D(), "points3d_valid_phase01_filter": len(valid_points), "filter_rejections": rejections, "tracks_ge_3": int((tracks >= 3).sum()), "track_length_median": float(np.median(tracks)) if len(tracks) else None, "point_error_p50": float(np.median(errors)) if len(errors) else None, "point_error_p90": float(np.percentile(errors, 90)) if len(errors) else None, "global_local_tracks_raw": bridge_count, "registered_local_without_global_track": sorted(local_names & present - bridged_local), "trajectory_max_rotation_deg": float(max(rotations)) if rotations else None, "trajectory_step_p99_over_median": float(np.quantile(steps, .99) / np.median(steps)) if steps and np.median(steps) > 0 else None, "plant_geometry_support": None, "plant_geometry_support_reason": "Candidate-specific multiview mask evidence is not human-verified", "cameras": [{"model": camera.model_name, "parameters": camera.params.tolist(), "focal_ratio": camera.mean_focal_length() / max(camera.width, camera.height), "bogus_parameters": bool(camera.has_bogus_params(.1, 10, 1))} for camera in cameras], "artifact_sha256": {name: sha256(Path(path) / f"{name}.bin") for name in names}, "scope": "FULL_SCENE_CANDIDATE; point counts and in-sample errors are not absolute reconstruction accuracy"}


def pareto_rows(rows):
    for item in rows:
        quality = (item["registered_images"], item["coverage"].get("LOCAL", {}).get("registered", 0), item["tracks_ge_3"], -(item["point_error_p90"] if item["point_error_p90"] is not None else float("inf")))
        item["pareto_dominated"] = any(other is not item and all(left >= right for left, right in zip((other["registered_images"], other["coverage"].get("LOCAL", {}).get("registered", 0), other["tracks_ge_3"], -(other["point_error_p90"] if other["point_error_p90"] is not None else float("inf"))), quality)) and any(left > right for left, right in zip((other["registered_images"], other["coverage"].get("LOCAL", {}).get("registered", 0), other["tracks_ge_3"], -(other["point_error_p90"] if other["point_error_p90"] is not None else float("inf"))), quality)) for other in rows)
    return rows


def audit_models(video_dir, destination):
    video_dir, destination = Path(video_dir), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    labels = pd.read_csv(video_dir / "segments" / "coarse_frame_labels.csv")
    rows = []
    for path in candidate_paths(video_dir / "sfm"):
        try:
            rows.append(summarize_candidate(path, labels))
        except Exception as exception:
            rows.append({"path": str(path), "read_error": f"{type(exception).__name__}: {exception}"})
    valid = pareto_rows([row for row in rows if "read_error" not in row])
    baseline = sorted(valid, key=lambda row: (-row["registered_images"], row["path"]))[0] if valid else None
    summary = {"selection_policy": "MAX_REGISTRATION_BASELINE: descending registered images, then lexicographic path; retain Pareto audit, no unvalidated weighted score", "baseline_selected": baseline["path"] if baseline else None, "phase01_final_path": str((video_dir / "sfm" / "final").resolve()), "candidates": rows, "count": len(rows), "pareto_count": sum(not row["pareto_dominated"] for row in valid)}
    write_json(destination / "model_selection_audit.json", summary)
    pd.DataFrame([{key: value for key, value in row.items() if key not in {"cameras", "artifact_sha256", "registered_filenames", "coverage"}} | {f"{label.lower()}_registered": stats["registered"] for label, stats in row.get("coverage", {}).items()} for row in rows]).to_csv(destination / "model_candidates.csv", index=False)
    return summary
