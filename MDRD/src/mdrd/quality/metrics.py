from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from mdrd.common import manifest_image_inputs, stage, write_json


def image_metrics(image, maximum=960, features=1600):
    if image is None or not image.size:
        raise ValueError("Unreadable or empty image")
    factor = min(1.0, maximum / max(image.shape))
    if factor < 1:
        image = cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
    intensity = image.astype(np.float32)
    gradient_x = cv2.Sobel(image, cv2.CV_32F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(image, cv2.CV_32F, 0, 1, ksize=3)
    local_mean = cv2.blur(intensity, (15, 15))
    local_std = np.sqrt(np.maximum(cv2.blur(intensity * intensity, (15, 15)) - local_mean ** 2, 0))
    detector = cv2.SIFT_create(nfeatures=features)
    keypoints, descriptors = detector.detectAndCompute(image, None)
    occupied = {(min(7, int(point.pt[0] / image.shape[1] * 8)), min(5, int(point.pt[1] / image.shape[0] * 6))) for point in keypoints}
    metrics = {"laplacian_variance": cv2.Laplacian(image, cv2.CV_64F).var(), "tenengrad": np.mean(gradient_x ** 2 + gradient_y ** 2), "mean_brightness": np.mean(image), "overexposed_ratio": np.mean(image >= 250), "underexposed_ratio": np.mean(image <= 5), "local_contrast": np.mean(local_std), "feature_count": len(keypoints), "feature_coverage": len(occupied) / 48, "analysis_width": image.shape[1], "analysis_height": image.shape[0]}
    return metrics, keypoints, descriptors


def adjacent_metrics(previous, image, previous_keypoints, keypoints, previous_descriptors, descriptors):
    result = {"feature_match_count": 0, "verified_match_count": 0, "feature_scale_ratio": np.nan, "scale_ratio_iqr": np.nan, "frame_motion_median": np.nan, "flow_expansion": np.nan, "flow_direction_distribution": "[]", "image_change_score": np.nan, "foreground_ratio": np.nan}
    if previous is None:
        return result
    result["image_change_score"] = float(np.mean(np.abs(image.astype(float) - previous.astype(float))) / 255)
    if previous_descriptors is not None and descriptors is not None and len(descriptors) >= 2:
        matches = cv2.BFMatcher().knnMatch(previous_descriptors, descriptors, k=2)
        good = [pair[0] for pair in matches if len(pair) == 2 and pair[0].distance < .75 * pair[1].distance]
        result["feature_match_count"] = len(good)
        if len(good) >= 8:
            source = np.float32([previous_keypoints[match.queryIdx].pt for match in good])
            target = np.float32([keypoints[match.trainIdx].pt for match in good])
            _, mask = cv2.findHomography(source, target, cv2.RANSAC, 3.0)
            if mask is not None:
                verified = [match for match, flag in zip(good, mask.ravel()) if flag]
                result["verified_match_count"] = len(verified)
                if len(verified) >= 12:
                    ratios = [keypoints[match.trainIdx].size / previous_keypoints[match.queryIdx].size for match in verified]
                    result["feature_scale_ratio"] = np.median(ratios)
                    result["scale_ratio_iqr"] = np.percentile(ratios, 75) - np.percentile(ratios, 25)
    corners = cv2.goodFeaturesToTrack(previous, maxCorners=600, qualityLevel=.01, minDistance=8)
    if corners is not None:
        tracked, status, _ = cv2.calcOpticalFlowPyrLK(previous, image, corners, None, winSize=(21, 21), maxLevel=3)
        back, backward_status, _ = cv2.calcOpticalFlowPyrLK(image, previous, tracked, None, winSize=(21, 21), maxLevel=3)
        valid = (status.ravel() == 1) & (backward_status.ravel() == 1) & (np.linalg.norm(back - corners, axis=2).ravel() < 1.5)
        source = corners[valid].reshape(-1, 2)
        displacement = tracked[valid].reshape(-1, 2) - source
        if len(source) >= 10:
            result["frame_motion_median"] = np.median(np.linalg.norm(displacement, axis=1))
            radial = source - np.array([image.shape[1] / 2, image.shape[0] / 2])
            denominator = np.sum(radial ** 2, axis=1)
            result["flow_expansion"] = np.median(np.sum(displacement * radial, axis=1) / np.maximum(denominator, 1))
            histogram, _ = np.histogram(np.arctan2(displacement[:, 1], displacement[:, 0]), bins=8, range=(-np.pi, np.pi))
            result["flow_direction_distribution"] = json.dumps((histogram / histogram.sum()).tolist())
    return result


def relative_quality_labels(frame, window=9):
    sharpness = np.log1p(frame.laplacian_variance)
    texture = np.log1p(frame.tenengrad)
    median = sharpness.rolling(window, center=True, min_periods=3).median()
    texture_median = texture.rolling(window, center=True, min_periods=3).median()
    sharpness_ratio = np.exp(sharpness - median)
    texture_ratio = np.exp(texture - texture_median)
    labels = np.full(len(frame), "UNCERTAIN", dtype=object)
    valid = median.notna() & texture_median.notna() & (frame.feature_count >= 40)
    labels[valid] = "CLEAR"
    labels[valid & (sharpness_ratio < .65) & (texture_ratio < .8)] = "MILD_BLUR"
    labels[valid & (sharpness_ratio < .3) & (texture_ratio < .5)] = "SEVERE_BLUR"
    return labels, sharpness_ratio, texture_ratio


def analyze_quality(directory, configuration, force=False):
    from mdrd.visualization.plots import contact_sheet, timeline

    directory = Path(directory)
    parameters = configuration["quality"]
    manifest_path = directory / "frame_manifest.csv"
    quality_dir = directory / "quality"
    quality_dir.mkdir(exist_ok=True)
    with stage(directory, "quality", parameters, [manifest_path, *manifest_image_inputs(manifest_path)], force, required_outputs=[quality_dir / "frame_quality.csv", quality_dir / "quality_summary.json"]) as execute:
        if not execute:
            return pd.read_csv(quality_dir / "frame_quality.csv")
        manifest = pd.read_csv(manifest_path)
        rows = []
        previous = previous_descriptors = previous_keypoints = None
        cv2.setNumThreads(2)
        for item in manifest.to_dict("records"):
            image = cv2.imread(item["image_path"], cv2.IMREAD_GRAYSCALE)
            factor = min(1.0, parameters["max_dimension"] / max(image.shape))
            if factor < 1:
                image = cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
            metrics, keypoints, descriptors = image_metrics(image, parameters["max_dimension"], parameters["features"])
            motion = adjacent_metrics(previous, image, previous_keypoints, keypoints, previous_descriptors, descriptors)
            rows.append({**item, **metrics, **motion})
            previous, previous_keypoints, previous_descriptors = image, keypoints, descriptors
        frame = pd.DataFrame(rows)
        labels, ratio, gradient_ratio = relative_quality_labels(frame, parameters["relative_window"])
        frame["quality_label"] = labels
        frame["relative_laplacian"] = ratio
        frame["relative_tenengrad"] = gradient_ratio
        frame["quality_scope"] = "FULL_SCENE_NO_FOREGROUND_MASK"
        frame.to_csv(quality_dir / "frame_quality.csv", index=False)
        timeline(frame, ["laplacian_variance", "tenengrad"], quality_dir / "sharpness_timeline.png")
        timeline(frame, ["mean_brightness", "overexposed_ratio", "underexposed_ratio"], quality_dir / "exposure_timeline.png")
        examples = frame.sort_values("relative_laplacian").head(6)
        contact_sheet(examples, quality_dir / "blur_examples.png", title="Lowest relative sharpness (not ground-truth blur)", columns=3)
        summary = {"frames": len(frame), "quality_counts": frame.quality_label.value_counts().to_dict(), "laplacian_median": frame.laplacian_variance.median(), "feature_count_median": frame.feature_count.median(), "limitation": "Full-scene relative temporal sharpness proxy. Texture/distance/content changes can confound labels; no verified foreground mask. Mild/severe candidates are retained, not deleted."}
        write_json(quality_dir / "quality_summary.json", summary)
        print(f"QUALITY {directory.name} {summary['quality_counts']}", flush=True)
        return frame
