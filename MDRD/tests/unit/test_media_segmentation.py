import numpy as np
import pandas as pd
import pytest

from mdrd.common import manifest_image_inputs, read_json, stage, write_json
from mdrd.quality.metrics import image_metrics, relative_quality_labels
from mdrd.segmentation.stages import apply_overrides, label_source_priority, refine_segments, runs, smooth_labels
from mdrd.video.media import choose_timestamp_indices, parse_showinfo


def test_vfr_nearest_timestamps_not_index_over_fps():
    times = [0, .018, .039, .081, .141, .213]
    selected = choose_timestamp_indices(times, [.04, .14, .22])
    assert selected.tolist() == [2, 4, 5]


def test_timestamp_empty_duplicate_targets_and_invalid_order():
    assert choose_timestamp_indices([], [1]).size == 0
    assert choose_timestamp_indices([0, .1, .2], [0, 0, .1]).tolist() == [0, 1]
    with pytest.raises(ValueError):
        choose_timestamp_indices([1, 0], [.5])


def test_showinfo_actual_pts_and_dimensions():
    text = "[showinfo@selected @ 0xabc] n:  2 pts: 301 pts_time:0.501667 fmt:rgb48be s:2160x3840 i:P iskey:0\n[showinfo@source @ 0xabc] n: 30 pts: 301 pts_time:0.501667 fmt:yuv420p10le s:2160x3840"
    result = parse_showinfo(text)
    assert result[0]["pts"] == 301
    assert result[0]["timestamp_sec"] == .501667
    assert result[0]["width"] == 2160 and result[0]["height"] == 3840
    assert parse_showinfo(text, "showinfo@source")[0]["source_frame_index"] == 30


def test_segment_empty_single_and_boundaries():
    assert runs([]) == []
    assert runs(["UNKNOWN"]) == [(0, 1, "UNKNOWN")]
    assert smooth_labels(["GLOBAL"] * 4 + ["LOCAL"] + ["GLOBAL"] * 4, 3).tolist() == ["GLOBAL"] * 4 + ["LOCAL"] + ["GLOBAL"] * 4
    assert smooth_labels(["LOCAL"] + ["GLOBAL"] * 4, 3).tolist()[0] == "LOCAL"


def test_approach_not_smoothed_away():
    labels = ["GLOBAL"] * 4 + ["APPROACH"] * 2 + ["LOCAL"] * 4
    assert smooth_labels(labels, 4)[4:6].tolist() == ["APPROACH", "APPROACH"]


def test_manual_override_retains_original_and_audit(tmp_path):
    frame = pd.DataFrame({"frame_id": [1, 2, 3], "timestamp_sec": [0, .5, 1.], "label": ["UNKNOWN"] * 3, "confidence": [.1] * 3, "label_source": ["AUTOMATIC"] * 3})
    original = frame.copy(deep=True)
    path = tmp_path / "override.json"
    write_json(path, [{"start_timestamp_sec": .4, "end_timestamp_sec": .9, "label": "GLOBAL", "source": "TEST_USER"}])
    output, version = apply_overrides(frame, path, tmp_path)
    pd.testing.assert_frame_equal(frame, original)
    assert output.label.tolist() == ["UNKNOWN", "GLOBAL", "UNKNOWN"]
    audit = read_json(tmp_path / "versions" / f"{version}.json")
    assert audit["changes"][0]["previous"] == [{"frame_id": 2, "label": "UNKNOWN"}]


def test_verified_human_override_requires_explicit_review_metadata(tmp_path):
    frame = pd.DataFrame({"frame_id": [1], "timestamp_sec": [0.], "label": ["UNKNOWN"], "confidence": [.1], "label_source": ["IMAGE_AUTO"]})
    path = tmp_path / "override.json"
    write_json(path, [{"start_timestamp_sec": 0, "end_timestamp_sec": 0, "label": "LOCAL", "source": "HUMAN_VERIFIED"}])
    with pytest.raises(ValueError, match="human_confirmed"):
        apply_overrides(frame, path, tmp_path)
    write_json(path, [{"start_timestamp_sec": 0, "end_timestamp_sec": 0, "label": "LOCAL", "source": "HUMAN_VERIFIED", "human_confirmed": True, "reviewed_by": "annotator-01"}])
    output, _ = apply_overrides(frame, path, tmp_path)
    assert output.label.iloc[0] == "LOCAL"
    assert output.label_source.iloc[0] == "HUMAN_VERIFIED"


def test_automated_review_cannot_be_promoted_to_human_verified(tmp_path):
    frame = pd.DataFrame({"frame_id": [1], "timestamp_sec": [0.], "label": ["UNKNOWN"], "confidence": [.1], "label_source": ["IMAGE_AUTO"]})
    path = tmp_path / "override.json"
    write_json(path, [{"start_timestamp_sec": 0, "end_timestamp_sec": 0, "label": "LOCAL", "source": "AGNES_API_FRAME_REVIEW_NOT_HUMAN_GROUND_TRUTH", "human_confirmed": True}])
    with pytest.raises(ValueError, match="cannot be marked human-confirmed"):
        apply_overrides(frame, path, tmp_path)


def test_label_source_priority_is_explicit():
    assert label_source_priority("HUMAN_VERIFIED") > label_source_priority("MANUAL_OVERRIDE")
    assert label_source_priority("MANUAL_OVERRIDE") > label_source_priority("EXTERNAL_VERIFIED_ANNOTATION")
    assert label_source_priority("EXTERNAL_VERIFIED_ANNOTATION") > label_source_priority("AGNES_API_FRAME_REVIEW_NOT_HUMAN_GROUND_TRUTH")
    assert label_source_priority("AUTOMATED_VISUAL_REVIEW") > label_source_priority("GEOMETRY_AUTO")


def test_manual_short_local_is_not_overwritten_by_refinement(tmp_path):
    folder = tmp_path / "sample" / "segments"
    folder.mkdir(parents=True)
    labels = ["GLOBAL"] * 3 + ["LOCAL"] * 2 + ["GLOBAL"] * 2
    sources = ["IMAGE_AUTO"] * 3 + ["MANUAL_OVERRIDE"] * 2 + ["IMAGE_AUTO"] * 2
    frame = pd.DataFrame({"frame_id": range(1, 8), "filename": [f"frame_{index:06d}.png" for index in range(1, 8)], "timestamp_sec": [index / 2 for index in range(7)], "label": labels, "confidence": [.8] * 7, "label_source": sources})
    frame.to_csv(folder / "coarse_frame_labels.csv", index=False)
    cameras = frame[["filename"]].copy()
    cameras["registered"] = True
    cameras["median_observed_depth"] = [10, 10, 10, 1, 1, 10, 10]
    cameras["median_ray_distance"] = [10, 10, 10, 1, 1, 10, 10]
    for name in ["camera_center_x", "camera_center_y", "camera_center_z"]:
        cameras[name] = 0.0
    cameras["observed_points"] = 100
    cameras["viewing_direction"] = None
    cameras["median_shared_global_distance_ratio"] = np.nan
    cameras["adjacent_sparse_jaccard"] = 1.0
    refined = refine_segments(folder.parent, cameras, {"segmentation": {"min_run": 4}})
    assert refined.label.iloc[3:5].tolist() == ["LOCAL", "LOCAL"]
    assert refined.label_source.iloc[3:5].tolist() == ["MANUAL_OVERRIDE", "MANUAL_OVERRIDE"]
    assert refined.refinement_change_reason.iloc[3:5].tolist() == ["AUTHORITATIVE_SHORT_LOCAL_PRESERVED"] * 2


def test_stage_cache_invalidates_if_image_changes_but_manifest_does_not(tmp_path):
    image = tmp_path / "frame.png"
    image.write_bytes(b"first-image-bytes")
    manifest = tmp_path / "frame_manifest.csv"
    manifest.write_text("image_path\nframe.png\n")
    image_inputs = manifest_image_inputs(manifest)
    with stage(tmp_path, "image-cache", {"threshold": 1}, [manifest, *image_inputs]) as execute:
        assert execute
    with stage(tmp_path, "image-cache", {"threshold": 1}, [manifest, *image_inputs]) as execute:
        assert not execute
    image.write_bytes(b"changed-image-bytes")
    with stage(tmp_path, "image-cache", {"threshold": 1}, [manifest, *image_inputs]) as execute:
        assert execute


def test_stage_cache_invalidates_when_required_output_changes(tmp_path):
    output = tmp_path / "result.json"
    with stage(tmp_path, "output-cache", {"v": 1}, required_outputs=[output]) as execute:
        assert execute
        output.write_text("original")
    with stage(tmp_path, "output-cache", {"v": 1}, required_outputs=[output]) as execute:
        assert not execute
    output.write_text("modified")
    with stage(tmp_path, "output-cache", {"v": 1}, required_outputs=[output]) as execute:
        assert execute


def test_visual_override_short_local_run_survives_refinement(tmp_path):
    from mdrd.segmentation.stages import refine_segments

    folder = tmp_path / "sample" / "segments"
    folder.mkdir(parents=True)
    frame = pd.DataFrame({"frame_id": range(1, 8), "filename": [f"frame_{idx:06d}.png" for idx in range(1, 8)], "timestamp_sec": [idx / 2 for idx in range(7)], "label": ["GLOBAL"] * 3 + ["LOCAL"] * 2 + ["GLOBAL"] * 2, "confidence": [.85] * 7, "label_source": ["AGNES_API_FRAME_REVIEW_NOT_HUMAN_GROUND_TRUTH"] * 7})
    frame.to_csv(folder / "coarse_frame_labels.csv", index=False)
    cameras = frame[["filename"]].copy()
    cameras["registered"] = False
    cameras["median_observed_depth"] = np.nan
    cameras["median_ray_distance"] = np.nan
    for name in ["camera_center_x", "camera_center_y", "camera_center_z"]:
        cameras[name] = np.nan
    cameras["observed_points"] = 0
    cameras["viewing_direction"] = None
    refined = refine_segments(folder.parent, cameras, {"segmentation": {"min_run": 4}})
    assert refined.label.tolist()[3:5] == ["LOCAL_01", "LOCAL_01"]
    assert not refined.geometry_validated.any()


def test_quality_relative_not_global_fixed_threshold():
    frame = pd.DataFrame({"laplacian_variance": [100] * 4 + [10] + [100] * 4, "tenengrad": [1000] * 4 + [50] + [1000] * 4, "feature_count": [300] * 9})
    labels, _, _ = relative_quality_labels(frame, 7)
    assert labels[4] == "SEVERE_BLUR"
    scaled = frame.copy()
    scaled["laplacian_variance"] *= 100
    scaled["tenengrad"] *= 100
    assert relative_quality_labels(scaled, 7)[0][4] == "SEVERE_BLUR"


def test_image_quality_empty_rejected():
    with pytest.raises(ValueError):
        image_metrics(np.zeros((0, 0), dtype=np.uint8))


def test_stage_resume_and_changed_input(tmp_path):
    source = tmp_path / "input.txt"
    source.write_text("first")
    with stage(tmp_path, "test", {"parameter": 1}, [source]) as execute:
        assert execute
    with stage(tmp_path, "test", {"parameter": 1}, [source]) as execute:
        assert not execute
    source.write_text("second")
    with stage(tmp_path, "test", {"parameter": 1}, [source]) as execute:
        assert execute


def test_stage_failure_does_not_cache_success(tmp_path):
    with pytest.raises(RuntimeError):
        with stage(tmp_path, "test", {}):
            raise RuntimeError("expected failure")
    assert read_json(tmp_path / "progress" / "test.json")["status"] == "failed"


def test_parallel_json_writes_have_unique_atomic_tempfiles(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    path = tmp_path / "shared.json"
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda index: write_json(path, {"index": index, "payload": "value" * 100}), range(40)))
    assert read_json(path)["index"] in range(40)
    assert not list(tmp_path.glob("*.tmp"))
