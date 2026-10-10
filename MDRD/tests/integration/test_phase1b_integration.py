import os
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pycolmap
import pytest

from mdrd.common import read_json, write_json
from mdrd.geometry.analysis import read_model_observations
from mdrd.phase1b.ablation import experiment_images
from mdrd.phase1b.evidence import align_models
from mdrd.phase1b.foreground import analyze_foreground


@pytest.mark.integration
def test_synthetic_region_track_and_bridge_inputs(tmp_path):
    test_root = Path(os.environ.get("MDRD_SYNTHETIC_SOURCE_ROOT", Path(__file__).resolve().parents[3] / "outputs" / "tests"))
    source = test_root / "synthetic_sfm" / "synthetic_known_scene"
    summary = read_json(source / "sfm" / "sfm_summary.json")
    reconstruction, poses, points, _, _, _, _ = read_model_observations(summary["model_path"])
    frame_names = pd.read_csv(source / "frame_manifest.csv").filename.tolist()
    target_id = next(point_id for point_id, point in points.items() if sum(poses[image_id]["name"] in frame_names[:4] for image_id in point["images"]) >= 2 and any(poses[image_id]["name"] in frame_names[6:8] for image_id in point["images"]))
    destination = tmp_path / "known_synthetic_not_real_video"
    (destination / "sfm").mkdir(parents=True)
    write_json(destination / "sfm" / "sfm_summary.json", {"model_path": summary["model_path"]})
    (destination / "segments").mkdir()
    (destination / "quality").mkdir()
    manifest = pd.read_csv(source / "frame_manifest.csv")
    manifest.to_csv(destination / "frame_manifest.csv", index=False)
    fixed = {"GLOBAL": frame_names[:4], "APPROACH": frame_names[4:6], "LOCAL": frame_names[6:8]}
    labels = manifest[["filename", "timestamp_sec", "frame_id"]].copy()
    labels["label"] = ["GLOBAL"] * 4 + ["APPROACH"] * 2 + ["LOCAL"] * 2
    labels["label_source"] = "KNOWN_SYNTHETIC_TEST_FIXTURE_NOT_HUMAN"
    labels.to_csv(destination / "segments" / "coarse_frame_labels.csv", index=False)
    labels.to_csv(destination / "segments" / "segment_confidence.csv", index=False)
    pd.DataFrame({"filename": frame_names, "quality_label": "CLEAR", "feature_count": 1500, "feature_coverage": .8}).to_csv(destination / "quality" / "frame_quality.csv", index=False)
    mask_dir = destination / "masks"
    mask_dir.mkdir()
    entries = []
    target = reconstruction.points3D[target_id]
    for image_id, pose in poses.items():
        image = reconstruction.images[image_id]
        camera = pose["camera"]
        mask = np.full((camera.height, camera.width), 2, np.uint8)
        for element in target.track.elements:
            if element.image_id == image_id:
                x, y = image.points2D[element.point2D_idx].xy
                cv2.circle(mask, (int(round(x)), int(round(y))), 3, 1, -1)
        path = mask_dir / f"{image.name}.png"
        cv2.imwrite(str(path), mask)
        entries.append({"mask_path": str(path), "image_path": str(source / "sfm_images" / image.name), "source": "SYNTHETIC_TARGET_MASK_NOT_REAL_VIDEO", "human_confirmed": False})
    write_json(destination / "masks.json", {"masks": entries})
    result = analyze_foreground(destination, destination / "foreground", destination / "masks.json")
    assert result["candidate_foreground_points"] >= 1
    assert result["verified_plant_geometry_available"] is False
    assert result["candidate_background_points"] >= 1
    assert len(pd.read_csv(destination / "foreground" / "foreground_pairs.csv")) > 0
    without_local = [row for row in entries if Path(row["image_path"]).name not in fixed["LOCAL"]]
    write_json(destination / "global_only_masks.json", {"masks": without_local})
    masked_global_only = analyze_foreground(destination, destination / "global_only_foreground", destination / "global_only_masks.json")
    assert masked_global_only["candidate_foreground_points"] >= 1
    assert masked_global_only["candidate_global_local_shared"] == 0
    write_json(destination / "empty_masks.json", {"masks": []})
    empty = analyze_foreground(destination, destination / "empty_foreground", destination / "empty_masks.json")
    assert empty["candidate_global_local_pair_angle_median_deg"] is None
    assert empty["candidate_track_length_median"] is None
    assert pd.read_csv(destination / "empty_foreground" / "foreground_pairs.csv").empty
    assert pd.read_csv(destination / "empty_foreground" / "per_image_foreground.csv").empty
    control = experiment_images(destination, destination / "supplement", destination / "M1", "M1", fixed)
    bridge = experiment_images(destination, destination / "supplement", destination / "M2", "M2", fixed)
    assert len(bridge["all_images"]) == len(control["all_images"]) + 2
    assert set(fixed["LOCAL"]).issubset(bridge["all_images"])
    assert align_models(summary["model_path"], summary["model_path"])["rms_residual"] < 1e-9
