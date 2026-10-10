import json

import cv2
import numpy as np
import pandas as pd
import pytest

from mdrd.common import read_json, stage, write_json
from mdrd.phase1b.ablation import adaptive_extra, experiment_images
from mdrd.phase1b.evidence import distinct_new_directions, fit_sim3, point_information
from mdrd.phase1b.foreground import BACKGROUND, PLANT_FOREGROUND, UNCERTAIN, classify_votes, import_mask, load_mask, mask_at_observation, verified_mask_provenance
from mdrd.phase1b.report import acceptance_status
from mdrd.phase1b.vision import propose_boxes
from mdrd.segmentation.stages import apply_overrides, smooth_labels


def test_verified_source_wins_against_automated_override(tmp_path):
    frame = pd.DataFrame([{"frame_id": 1, "timestamp_sec": 1., "label": "LOCAL", "confidence": 1., "label_source": "HUMAN_VERIFIED"}])
    path = tmp_path / "override.json"
    write_json(path, [{"start_timestamp_sec": 1, "end_timestamp_sec": 1, "label": "GLOBAL", "source": "AUTOMATED_VISUAL_REVIEW"}])
    result, _ = apply_overrides(frame, path, tmp_path)
    assert result.label.iloc[0] == "LOCAL"
    assert result.label_source.iloc[0] == "HUMAN_VERIFIED"


def test_external_verified_source_requires_reviewer(tmp_path):
    frame = pd.DataFrame([{"frame_id": 1, "timestamp_sec": 0., "label": "UNKNOWN", "confidence": .1}])
    path = tmp_path / "override.json"
    write_json(path, [{"start_timestamp_sec": 0, "end_timestamp_sec": 0, "label": "LOCAL", "source": "EXTERNAL_VERIFIED_ANNOTATION"}])
    with pytest.raises(ValueError, match="reviewed_by"):
        apply_overrides(frame, path, tmp_path)


def test_short_automatic_local_is_not_smoothed_away():
    assert smooth_labels(["GLOBAL", "LOCAL", "GLOBAL"], minimum=4).tolist() == ["GLOBAL", "LOCAL", "GLOBAL"]


def test_foreground_mask_orientation_and_class_validation(tmp_path):
    path = tmp_path / "mask.png"
    cv2.imwrite(str(path), np.ones((8, 12), np.uint8))
    assert mask_at_observation(load_mask(path, (12, 8)), (2, 3)) == PLANT_FOREGROUND
    with pytest.raises(ValueError, match="size/class/orientation"):
        load_mask(path, (8, 12))
    cv2.imwrite(str(path), np.full((8, 12), 255, np.uint8))
    with pytest.raises(ValueError, match="size/class/orientation"):
        load_mask(path, (12, 8))


def test_mask_outside_image_is_uncertain(tmp_path):
    path = tmp_path / "mask.png"
    cv2.imwrite(str(path), np.full((2, 2), PLANT_FOREGROUND, np.uint8))
    assert mask_at_observation(load_mask(path, (2, 2)), (-1, 0)) == UNCERTAIN
    assert mask_at_observation(load_mask(path, (2, 2)), (np.nan, 1)) == UNCERTAIN


@pytest.mark.parametrize("votes,expected", [([1, 1, 0], "PLANT_FOREGROUND"), ([2, 2, 0], "BACKGROUND"), ([1, 2, 1], "UNCERTAIN"), ([1], "UNCERTAIN"), ([], "UNCERTAIN")])
def test_multiview_votes_never_force_conflicts_or_singletons(votes, expected):
    assert classify_votes(votes)["class"] == expected


def test_auto_masks_cannot_be_imported_as_verified_without_reviewer(tmp_path):
    image = tmp_path / "image.png"
    mask = tmp_path / "mask.png"
    cv2.imwrite(str(image), np.zeros((3, 4, 3), np.uint8))
    cv2.imwrite(str(mask), np.ones((3, 4), np.uint8))
    with pytest.raises(ValueError, match="named reviewer"):
        import_mask(image, mask, tmp_path / "out.png", "HUMAN_VERIFIED")
    result = import_mask(image, mask, tmp_path / "out.png", "PROVISIONAL_AUTO")
    assert result["human_confirmed"] is False


def test_automatic_mask_cannot_claim_external_human_provenance():
    with pytest.raises(ValueError, match="authoritative source"):
        verified_mask_provenance({"source": "PROVISIONAL_AUTO_AGNES", "human_confirmed": True, "reviewed_by": "bot"})
    with pytest.raises(ValueError, match="authoritative source"):
        verified_mask_provenance({"source": "HUMAN_VERIFIED", "human_confirmed": False, "reviewed_by": "reviewer"})
    assert verified_mask_provenance({"source": "HUMAN_VERIFIED", "human_confirmed": True, "reviewed_by": "reviewer"})


def test_visual_api_cannot_override_provenance_fields(tmp_path, monkeypatch):
    video = tmp_path / "video"
    (video / "sfm_images").mkdir(parents=True)
    cv2.imwrite(str(video / "sfm_images" / "frame_000001.png"), np.zeros((3, 4, 3), np.uint8))
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": json.dumps({"box_xyxy_normalized": [0, 0, 1, 1], "plant_visible": True, "human_confirmed": True, "source": "HUMAN_VERIFIED", "status": "HUMAN_VERIFIED"})}}]}
    monkeypatch.setenv("AGNES_API_KEY", "test-token-not-a-real-key")
    monkeypatch.setattr("mdrd.phase1b.vision.requests.post", lambda *args, **kwargs: Response())
    result = propose_boxes(video, tmp_path / "proposals", [1], workers=1)[0]
    assert result["human_confirmed"] is False
    assert result["source"] == "AGNES_API_AUTOMATED_NOT_HUMAN"
    assert result["status"] == "PROVISIONAL_AUTO"


def test_mask_change_invalidates_geometry_without_changing_images(tmp_path):
    image, mask = tmp_path / "frame.png", tmp_path / "mask.png"
    image.write_bytes(b"image unchanged")
    mask.write_bytes(b"mask first")
    with stage(tmp_path, "foreground", {}, [image, mask]) as run:
        assert run
    with stage(tmp_path, "foreground", {}, [image, mask]) as run:
        assert not run
    mask.write_bytes(b"mask changed")
    with stage(tmp_path, "foreground", {}, [image, mask]) as run:
        assert run


def test_directory_model_artifact_change_invalidates_stage(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    (model / "points3D.bin").write_bytes(b"first")
    with stage(tmp_path, "analyze", {}, [model]) as run:
        assert run
    with stage(tmp_path, "analyze", {}, [model]) as run:
        assert not run
    (model / "points3D.bin").write_bytes(b"changed")
    with stage(tmp_path, "analyze", {}, [model]) as run:
        assert run


def test_newly_discovered_model_outputs_are_cached_on_first_run(tmp_path):
    model = tmp_path / "points3D.bin"
    def outputs():
        return [model] if model.exists() else []
    with stage(tmp_path, "dynamic-output-test", {}, required_outputs=outputs) as run:
        assert run
        model.write_bytes(b"first model")
    with stage(tmp_path, "dynamic-output-test", {}, required_outputs=outputs) as run:
        assert not run
    model.write_bytes(b"second model")
    with stage(tmp_path, "dynamic-output-test", {}, required_outputs=outputs) as run:
        assert run


def test_sim3_recovers_scale_rotation_translation():
    source = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
    rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    target = (2.5 * (rotation @ source.T)).T + [3., -1., 2.]
    result = fit_sim3(source, target)
    assert result["scale"] == pytest.approx(2.5)
    np.testing.assert_allclose(result["rotation"], rotation, atol=1e-10)
    assert result["rms_residual"] < 1e-10


def test_sim3_rejects_degenerate_centers():
    with pytest.raises(ValueError, match="Degenerate"):
        fit_sim3([[0, 0, 0]] * 3, [[1, 1, 1]] * 3)


def test_same_point_new_direction_distinguishes_duplicate():
    point = np.array([0., 0., 10.])
    angles = distinct_new_directions(point, [np.array([0., 0., 0.])], [np.array([0., 0., 0.]), np.array([2., 0., 0.])])
    assert angles[0] == pytest.approx(0)
    assert angles[1] > 10


def test_empty_information_has_no_gain():
    assert point_information([0, 0, 1], []) is None
    rows = [{"stage": "GLOBAL", "time": 0., "jacobian": [[1, 0, 0], [0, 1, 0]]}, {"stage": "LOCAL", "time": .1, "jacobian": [[0, 1, 0], [0, 0, 1]]}]
    full = point_information([0, 0, 1], rows)
    decimated = point_information([0, 0, 1], rows, effective_gap_sec=.5)
    assert full["GLOBAL_LOCAL"]["rank"] == 3
    assert decimated["GLOBAL_LOCAL"]["rank"] == 2


def test_adaptive_frames_exclude_target_local_interval():
    frame = pd.DataFrame({"filename": ["bridge.jpg", "target.jpg"], "timestamp_sec": [1., 2.], "sharpness": [10., 200.]})
    assert adaptive_extra(frame, excluded_intervals=[(1.5, 2.5)]) == ["bridge.jpg"]


def test_experiments_do_not_reuse_incompatible_image_set(tmp_path):
    video = tmp_path / "video"
    video.mkdir()
    pd.DataFrame([{"filename": "frame_1.png", "timestamp_sec": 0, "image_path": "not-read", "file_sha256": "a"}]).to_csv(video / "frame_manifest.csv", index=False)
    (video / "segments").mkdir()
    pd.DataFrame([{"filename": "frame_1.png", "timestamp_sec": 0, "label": "GLOBAL"}]).to_csv(video / "segments" / "coarse_frame_labels.csv", index=False)
    (video / "quality").mkdir()
    pd.DataFrame([{"filename": "frame_1.png", "quality_label": "CLEAR", "feature_count": 200, "feature_coverage": .8}]).to_csv(video / "quality" / "frame_quality.csv", index=False)
    fixed = {"GLOBAL": ["frame_1.png"], "LOCAL": [], "APPROACH": []}
    experiment_images(video, tmp_path / "supplement", tmp_path / "M1", "M1", fixed)
    with pytest.raises(ValueError, match="different input set"):
        experiment_images(video, tmp_path / "supplement", tmp_path / "M1", "M2", fixed)


def test_engineering_status_is_independent_of_research_readiness():
    engineering = {"data_available": True, "phase01_modified": False, "test_failure": False, "tested": True, "all_sample_ablations": True, "outputs_present": True}
    research = {"local_intervals_reviewed": False, "plant_masks_verified": False, "controlled_ablations": True}
    assert acceptance_status(engineering, research) == ("PASS", "INSUFFICIENT")
    engineering["test_failure"] = True
    assert acceptance_status(engineering, {key: True for key in research}) == ("FAIL", "READY")
