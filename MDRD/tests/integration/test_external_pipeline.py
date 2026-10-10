import os
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pycolmap
import pytest
from scipy.linalg import orthogonal_procrustes

from mdrd.common import load_config, read_json, run_command, sha256, write_json
from mdrd.geometry.analysis import analyze, read_model_observations
from mdrd.geometry.core import triangulation_angles
from mdrd.quality import analyze_quality
from mdrd.reporting.reports import sample_report
from mdrd.sfm import run_sfm
from mdrd.video.media import extract, probe


TEST_ROOT = Path(os.environ.get("MDRD_TEST_OUTPUT_ROOT", Path(__file__).resolve().parents[3] / "outputs" / "phase1b" / "tests" / "fixtures"))


@pytest.mark.integration
def test_ffmpeg_vfr_pts_manifest():
    output = TEST_ROOT / "vfr"
    output.mkdir(parents=True, exist_ok=True)
    video = output / "SYNTHETIC_TEST_ONLY.mp4"
    run_command(["ffmpeg", "-hide_banner", "-y", "-f", "lavfi", "-i", "testsrc2=duration=3:size=320x240:rate=4", "-vf", "settb=expr=1/1000,setpts=N*250+if(gte(N\,4)\,130\,0)", "-fps_mode", "passthrough", "-enc_time_base", "1:1000", "-c:v", "libx264", "-video_track_timescale", "1000", "-threads", "2", str(video)], output / "create_vfr.log")
    metadata = probe(video)
    configuration = load_config(overrides={"output_root": str(output), "sampling": {"fps": 2, "max_images": 20}})
    record = {"video_id": "synthetic_vfr", "source_path": str(video), "duration_sec": float(metadata["format"]["duration"]), "file_sha256": sha256(video), "time_base": metadata["streams"][0]["time_base"]}
    manifest = extract(record, configuration, force=True)
    assert metadata["timestamp_diagnostics"]["variable_cadence"]
    source_times = {float(packet["pts_time"]) for packet in metadata["packets"]}
    assert all(any(abs(timestamp - original) < 1e-5 for original in source_times) for timestamp in manifest.timestamp_sec)
    assert not np.allclose(manifest.timestamp_sec, (manifest.frame_id - 1) / 2)
    assert manifest.file_sha256.map(len).eq(64).all()
    assert manifest.timestamp_sec.is_monotonic_increasing
    baseline_indices = set(manifest.source_frame_index)
    supplemented = extract(record, configuration, force=True, supplemental_times=[.25, .75])
    assert baseline_indices.issubset(set(supplemented.source_frame_index))
    assert len(supplemented) > len(manifest)
    configuration["sampling"]["target_count"] = 5
    targeted = extract(record, configuration, force=True)
    assert len(targeted) == 5


def render_known_scene(directory):
    directory.mkdir(parents=True, exist_ok=True)
    frames = directory / "frames"
    frames.mkdir(exist_ok=True)
    generator = np.random.default_rng(731)
    width, height, focal = 640, 480, 580
    centers = np.column_stack([np.linspace(-.85, .85, 8), np.zeros(8), np.zeros(8)])
    patches = []
    for depth in [2.8, 3.6, 4.7]:
        for horizontal in np.linspace(-1.6, 1.6, 8):
            for vertical in np.linspace(-.9, .9, 5):
                texture = generator.integers(0, 256, (48, 48, 3), dtype=np.uint8)
                texture = cv2.GaussianBlur(texture, (3, 3), .6)
                cv2.circle(texture, (24, 24), 9, tuple(int(value) for value in generator.integers(0, 256, 3)), 2)
                patches.append((np.array([horizontal, vertical, depth]), texture))
    records = []
    for index, center in enumerate(centers, 1):
        image = np.full((height, width, 3), 28, np.uint8)
        for point, texture in sorted(patches, key=lambda item: -item[0][2]):
            projected = focal * (point[:2] - center[:2]) / point[2] + [width / 2, height / 2]
            size = int(round(focal * .27 / point[2]))
            start = np.round(projected - size / 2).astype(int)
            stop = start + size
            if start[0] >= 0 and start[1] >= 0 and stop[0] < width and stop[1] < height:
                image[start[1]:stop[1], start[0]:stop[0]] = cv2.resize(texture, (size, size))
        path = frames / f"frame_{index:06d}.png"
        cv2.imwrite(str(path), image)
        records.append({"video_id": "synthetic_known_scene", "frame_id": index, "filename": path.name, "timestamp_sec": (index - 1) * .5, "image_path": str(path.resolve()), "width": width, "height": height, "sampling_method": "SYNTHETIC_TEST_FIXTURE_NOT_REAL_VIDEO", "file_sha256": sha256(path)})
    manifest = pd.DataFrame(records)
    manifest.to_csv(directory / "frame_manifest.csv", index=False)
    write_json(directory / "ground_truth.json", {"synthetic": True, "seed": 731, "camera_centers": centers, "rotation_world_to_camera": np.eye(3), "intrinsics": [focal, focal, width / 2, height / 2], "note": "Programmatic textured noncoplanar patch scene; never counted as real-video experiment."})
    return manifest, centers, focal


@pytest.mark.integration
def test_colmap_known_trajectory_geometry_and_report():
    output = TEST_ROOT / "synthetic_sfm"
    directory = output / "synthetic_known_scene"
    manifest, expected, focal = render_known_scene(directory)
    known_calibration = {"--Mapper.ba_refine_focal_length": "0", "--Mapper.ba_refine_principal_point": "0", "--Mapper.ba_refine_extra_params": "0", "--random_seed": "731"}
    extra_options = {name: known_calibration.copy() for name in ("mapper", "image_registrator", "point_triangulator")}
    extra_options["feature_extractor"] = {"--ImageReader.camera_params": f"{focal},320,240,0"}
    extra_options["exhaustive_matcher"] = {"--random_seed": "731"}
    extra_options["bundle_adjuster"] = {"--BundleAdjustment.refine_focal_length": "0", "--BundleAdjustment.refine_principal_point": "0", "--BundleAdjustment.refine_extra_params": "0", "--random_seed": "731"}
    configuration = load_config(overrides={"output_root": str(output), "sfm": {"threads": 4, "max_image_size": 640, "max_num_features": 2400, "extra_options": extra_options}})
    analyze_quality(directory, configuration, force=True)
    segment_dir = directory / "segments"
    segment_dir.mkdir(exist_ok=True)
    labels = manifest[["video_id", "frame_id", "filename", "timestamp_sec"]].copy()
    labels["label"] = "GLOBAL"
    labels["confidence"] = 1.0
    labels["label_source"] = "KNOWN_SYNTHETIC_FIXTURE"
    labels.to_csv(segment_dir / "coarse_frame_labels.csv", index=False)
    write_json(segment_dir / "coarse_segments.json", {"synthetic": True, "frames": labels.to_dict("records")})
    summary = run_sfm(directory, configuration, force=True)
    assert summary["model_path"] is not None
    reconstruction = pycolmap.Reconstruction(summary["model_path"])
    assert reconstruction.num_reg_images() >= 6
    for camera in reconstruction.cameras.values():
        np.testing.assert_allclose(camera.params, [focal, 320, 240, 0], atol=1e-8)
    actual_rows, expected_rows = [], []
    for image_id in reconstruction.reg_image_ids():
        image = reconstruction.images[image_id]
        index = int(Path(image.name).stem.split("_")[-1]) - 1
        actual_rows.append(image.projection_center())
        expected_rows.append(expected[index])
    actual = np.array(actual_rows)
    truth = np.array(expected_rows)
    actual -= actual.mean(axis=0)
    truth -= truth.mean(axis=0)
    actual /= np.linalg.norm(actual)
    truth /= np.linalg.norm(truth)
    rotation, _ = orthogonal_procrustes(actual, truth)
    assert np.sqrt(np.mean((actual @ rotation - truth) ** 2)) < .12
    diagnosis = analyze(directory, configuration, force=True)
    assert diagnosis["valid_3d_points"] > 30
    pairs = pd.read_csv(directory / "geometry" / "pairwise_geometry.csv")
    assert pairs.geometry_valid.sum() > 0
    reconstruction, poses, points, observations, _, _, _ = read_model_observations(summary["model_path"])
    measured = pairs[pairs.geometry_valid].iloc[0]
    common = observations[int(measured.image_id_i)] & observations[int(measured.image_id_j)]
    xyz = np.array([points[point_id]["xyz"] for point_id in common])
    angles = triangulation_angles(poses[int(measured.image_id_i)]["center"], poses[int(measured.image_id_j)]["center"], xyz)
    assert measured.angle_median == pytest.approx(np.median(angles), rel=1e-8)
    assert measured.common_3d_points == len(common)
    source = {"filename": "SYNTHETIC_TEST_ONLY", "file_sha256": "not_a_real_video", "duration_sec": 3.5, "synthetic": True}
    sample_report(directory, source)
    assert (directory / "report" / "diagnosis.md").exists()
    assert "合成集成测试（非真实视频）" in (directory / "report" / "diagnosis.md").read_text()
