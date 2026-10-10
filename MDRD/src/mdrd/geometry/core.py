from __future__ import annotations

import numpy as np


def camera_center(rotation, translation):
    rotation = np.asarray(rotation, dtype=float).reshape(3, 3)
    translation = np.asarray(translation, dtype=float).reshape(3)
    if not np.all(np.isfinite(rotation)) or not np.all(np.isfinite(translation)):
        raise ValueError("Non-finite world-to-camera transformation")
    if not np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-6) or not np.isclose(np.linalg.det(rotation), 1, atol=1e-6):
        raise ValueError("Rotation must be a proper orthogonal matrix")
    return -rotation.T @ translation


def world_to_camera(points, rotation, translation):
    return np.asarray(points, dtype=float) @ np.asarray(rotation, dtype=float).T + np.asarray(translation, dtype=float)


def camera_to_world(points, rotation, translation):
    return (np.asarray(points, dtype=float) - np.asarray(translation, dtype=float)) @ np.asarray(rotation, dtype=float)


def project_pinhole(points, intrinsics, rotation=None, translation=None):
    values = np.asarray(points, dtype=float).reshape(-1, 3)
    if rotation is not None:
        values = world_to_camera(values, rotation, translation)
    valid = np.all(np.isfinite(values), axis=1) & (values[:, 2] > 1e-9)
    result = np.full((len(values), 2), np.nan)
    homogeneous = values[valid] @ np.asarray(intrinsics, dtype=float).T
    result[valid] = homogeneous[:, :2] / homogeneous[:, 2:3]
    return result, valid


def backproject_pinhole(pixels, depth, intrinsics, rotation=None, translation=None):
    pixels = np.asarray(pixels, dtype=float).reshape(-1, 2)
    depths = np.broadcast_to(np.asarray(depth, dtype=float), (len(pixels),))
    rays = np.column_stack([pixels, np.ones(len(pixels))]) @ np.linalg.inv(intrinsics).T
    values = rays / rays[:, 2:3] * depths[:, None]
    values[~np.isfinite(depths) | (depths <= 0)] = np.nan
    return camera_to_world(values, rotation, translation) if rotation is not None else values


def triangulation_angles(first_center, second_center, points):
    values = np.asarray(points, dtype=float).reshape(-1, 3)
    first = values - np.asarray(first_center)
    second = values - np.asarray(second_center)
    denominator = np.linalg.norm(first, axis=1) * np.linalg.norm(second, axis=1)
    valid = np.isfinite(denominator) & (denominator > 1e-12) & np.all(np.isfinite(values), axis=1)
    angles = np.full(len(values), np.nan)
    cosine = np.sum(first[valid] * second[valid], axis=1) / denominator[valid]
    angles[valid] = np.degrees(np.arccos(np.clip(cosine, -1, 1)))
    return angles


def baseline_depth_ratio(first_center, second_center, points):
    values = np.asarray(points, dtype=float).reshape(-1, 3)
    depths = (np.linalg.norm(values - np.asarray(first_center), axis=1) + np.linalg.norm(values - np.asarray(second_center), axis=1)) / 2
    baseline = np.linalg.norm(np.asarray(first_center) - np.asarray(second_center))
    ratios = np.full(len(values), np.nan)
    valid = np.isfinite(depths) & (depths > 1e-12)
    ratios[valid] = baseline / depths[valid]
    return ratios


def covisibility(first, second):
    if first is None or second is None:
        return {"common_points": np.nan, "jaccard": np.nan, "coverage_i_j": np.nan, "coverage_j_i": np.nan}
    first = set(first)
    second = set(second)
    common = len(first & second)
    union = len(first | second)
    return {"common_points": common, "jaccard": common / union if union else np.nan, "coverage_i_j": common / len(first) if first else np.nan, "coverage_j_i": common / len(second) if second else np.nan}


def pair_statistics(first_center, second_center, points, errors=None, minimum=1):
    values = np.asarray(points, dtype=float).reshape(-1, 3)
    result = {"baseline": float(np.linalg.norm(np.asarray(first_center) - np.asarray(second_center))), "median_baseline_depth_ratio": np.nan, "angle_p10": np.nan, "angle_median": np.nan, "angle_p90": np.nan, "common_3d_points": len(values), "reprojection_error": np.nan, "geometry_valid": False}
    if len(values) < minimum:
        return result
    angles = triangulation_angles(first_center, second_center, values)
    ratios = baseline_depth_ratio(first_center, second_center, values)
    valid = np.isfinite(angles) & np.isfinite(ratios)
    result["common_3d_points"] = int(np.sum(valid))
    if np.sum(valid) < minimum:
        return result
    result.update(median_baseline_depth_ratio=np.median(ratios[valid]), angle_p10=np.percentile(angles[valid], 10), angle_median=np.median(angles[valid]), angle_p90=np.percentile(angles[valid], 90), geometry_valid=True)
    if errors is not None:
        result["reprojection_error"] = np.median(np.asarray(errors)[valid])
    return result


def broad_label(label):
    if str(label).startswith("LOCAL") or label == "TOP_CANDIDATE":
        return "LOCAL"
    return str(label)


def pair_group(first, second):
    labels = [broad_label(first), broad_label(second)]
    if labels[0] == labels[1] and labels[0] in {"GLOBAL", "LOCAL"}:
        return labels[0] + "_" + labels[1]
    pair = set(labels)
    for first_label, second_label in [("GLOBAL", "LOCAL"), ("GLOBAL", "APPROACH"), ("APPROACH", "LOCAL")]:
        if pair == {first_label, second_label}:
            return f"{first_label}_{second_label}"
    return "OTHER"
