import numpy as np
import pandas as pd
import pytest
from scipy.spatial.transform import Rotation

from mdrd.geometry.analysis import camera_table, pairwise_analysis, read_model_observations
from mdrd.geometry.core import backproject_pinhole, baseline_depth_ratio, camera_center, camera_to_world, covisibility, pair_group, pair_statistics, project_pinhole, triangulation_angles, world_to_camera


def test_camera_center_rotated_translation():
    rotation = Rotation.from_euler("xyz", [13, 40, -27], degrees=True).as_matrix()
    expected = np.array([2., -3., 7.])
    translation = -rotation @ expected
    np.testing.assert_allclose(camera_center(rotation, translation), expected, atol=1e-12)
    np.testing.assert_allclose(world_to_camera(expected, rotation, translation), [0, 0, 0], atol=1e-12)


def test_invalid_rotation_rejected():
    with pytest.raises(ValueError):
        camera_center(np.diag([1, 1, -1]), [0, 0, 0])


def test_coordinate_round_trip():
    rotation = Rotation.from_euler("y", 30, degrees=True).as_matrix()
    points = np.array([[1, 2, 3], [-4, 5, 6]])
    translation = np.array([2, 0, 1])
    np.testing.assert_allclose(camera_to_world(world_to_camera(points, rotation, translation), rotation, translation), points)


def test_projection_and_backprojection():
    intrinsics = np.array([[500., 0, 320], [0, 510, 240], [0, 0, 1]])
    rotation = Rotation.from_euler("y", 10, degrees=True).as_matrix()
    translation = np.array([.1, -.2, 1.])
    points = np.array([[.1, .2, 3.], [-.4, .5, 4.]])
    pixels, valid = project_pinhole(points, intrinsics, rotation, translation)
    assert valid.all()
    depths = world_to_camera(points, rotation, translation)[:, 2]
    np.testing.assert_allclose(backproject_pinhole(pixels, depths, intrinsics, rotation, translation), points, atol=1e-12)


def test_nonpositive_depth_filters():
    pixels, valid = project_pinhole([[0, 0, -1], [0, 0, 0], [np.nan, 0, 1], [0, 0, 1]], np.eye(3))
    assert valid.tolist() == [False, False, False, True]
    assert np.isnan(pixels[:3]).all()
    assert np.isnan(backproject_pinhole([[0, 0]], -1, np.eye(3))).all()


def test_exact_right_angle_rays():
    angles = triangulation_angles([-1, 0, 0], [1, 0, 0], [[0, 0, 1]])
    np.testing.assert_allclose(angles, [90], atol=1e-10)


def test_baseline_depth_ratio_known():
    np.testing.assert_allclose(baseline_depth_ratio([-1, 0, 0], [1, 0, 0], [[0, 0, 1]]), [np.sqrt(2)])


@pytest.mark.parametrize("scale", [.01, 7.5, 1000])
def test_scale_invariance(scale):
    first = np.array([-.4, .1, .2])
    second = np.array([.7, -.3, .1])
    points = np.array([[.2, .1, 4.], [.5, .2, 3.]])
    offset = np.array([23, -7, 9])
    np.testing.assert_allclose(triangulation_angles(first, second, points), triangulation_angles(scale * first + offset, scale * second + offset, scale * points + offset), atol=1e-8)
    np.testing.assert_allclose(baseline_depth_ratio(first, second, points), baseline_depth_ratio(scale * first + offset, scale * second + offset, scale * points + offset), atol=1e-8)


def test_empty_points_and_missing_angles():
    assert len(triangulation_angles([0, 0, 0], [1, 0, 0], [])) == 0
    result = pair_statistics([0, 0, 0], [1, 0, 0], [], minimum=1)
    assert result["common_3d_points"] == 0
    assert not result["geometry_valid"]
    assert np.isnan(result["angle_median"])


def test_ray_from_camera_center_is_invalid():
    assert np.isnan(triangulation_angles([0, 0, 0], [1, 0, 0], [[0, 0, 0]])[0])


def test_covisibility_intersection():
    result = covisibility({1, 2, 3}, {2, 3, 4, 5})
    assert result["common_points"] == 2
    assert result["jaccard"] == pytest.approx(2 / 5)
    assert result["coverage_i_j"] == pytest.approx(2 / 3)
    assert result["coverage_j_i"] == pytest.approx(2 / 4)


def test_empty_and_unregistered_covisibility():
    empty = covisibility(set(), set())
    assert empty["common_points"] == 0
    assert np.isnan(empty["jaccard"])
    assert np.isnan(covisibility(None, {1})["common_points"])


def test_disjoint_nonempty_covisibility_is_zero():
    result = covisibility({1}, {2})
    assert result["jaccard"] == 0
    assert result["coverage_i_j"] == 0


def test_pair_group_symmetric_and_local_instances():
    assert pair_group("LOCAL_02", "GLOBAL") == "GLOBAL_LOCAL"
    assert pair_group("LOCAL_01", "LOCAL_03") == "LOCAL_LOCAL"
    assert pair_group("APPROACH", "LOCAL_01") == "APPROACH_LOCAL"
    assert pair_group("UNKNOWN", "GLOBAL") == "OTHER"


def test_unregistered_camera_is_preserved():
    manifest = pd.DataFrame([{"filename": "unregistered.png", "frame_id": 1, "timestamp_sec": .517}])
    coarse = pd.DataFrame([{"filename": "unregistered.png", "label": "LOCAL"}])
    database = pd.DataFrame([{"name": "unregistered.png", "image_id": 5, "camera_id": 1}])
    frame = camera_table(manifest, coarse, database, {}, {}, {}, {})
    assert len(frame) == 1 and not frame.iloc[0].registered
    assert frame.iloc[0].image_id == 5
    assert np.isnan(frame.iloc[0].camera_center_x)


def test_unregistered_pair_remains_missing():
    camera_rows = pd.DataFrame([{"filename": "a", "frame_id": 1, "timestamp_sec": 0, "image_id": 1, "registered": False, "segment": "GLOBAL"}, {"filename": "b", "frame_id": 2, "timestamp_sec": .5, "image_id": 2, "registered": False, "segment": "LOCAL_01"}])
    pairs, counts, jaccard, directional = pairwise_analysis(camera_rows, {}, {}, {}, {"temporal_block_sec": 3, "min_common_points": 20})
    assert len(pairs) == 1
    assert np.isnan(pairs.iloc[0].angle_median)
    assert np.isnan(counts).all() and np.isnan(jaccard).all() and np.isnan(directional).all()


def test_real_model_observation_filter_for_negative_depth_and_residual(tmp_path):
    (tmp_path / "cameras.txt").write_text("1 SIMPLE_PINHOLE 100 100 100 50 50\n")
    (tmp_path / "images.txt").write_text("1 1 0 0 0 0 0 0 1 a.png\n50 50 1 50 50 2 99 99 3\n2 1 0 0 0 -1 0 0 1 b.png\n30 50 1 70 50 2 99 99 3\n")
    (tmp_path / "points3D.txt").write_text("1 0 0 5 255 255 255 0 1 0 2 0\n2 0 0 -5 255 255 255 0 1 1 2 1\n3 1 0 5 255 255 255 0 1 2 2 2\n")
    _, _, points, observations, _, _, rejected = read_model_observations(tmp_path, maximum_error=4, minimum_track=2)
    assert set(points) == {1}
    assert observations[1] == {1} and observations[2] == {1}
    assert rejected["nonpositive_depth"] == 2
    assert rejected["high_observation_error"] == 2
