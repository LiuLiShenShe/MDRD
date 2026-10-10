from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from mdrd.common import now, read_json, sha256, stage, write_json
from mdrd.visualization.plots import segment_timeline, timeline


def runs(labels):
    values = list(labels)
    if not values:
        return []
    boundaries = [0] + [index for index in range(1, len(values)) if values[index] != values[index - 1]] + [len(values)]
    return [(start, stop, values[start]) for start, stop in zip(boundaries[:-1], boundaries[1:])]


def smooth_labels(labels, minimum=4):
    values = np.array(labels, dtype=object).copy()
    for start, stop, label in runs(values):
        if stop - start >= minimum or len(values) < minimum:
            continue
        left = values[start - 1] if start else None
        right = values[stop] if stop < len(values) else None
        if left is not None and left == right:
            values[start:stop] = left
        elif label not in {"APPROACH", "TRANSITION"}:
            values[start:stop] = "UNKNOWN"
    return values


def segment_records(frame, column="label"):
    result = []
    for index, (start, stop, label) in enumerate(runs(frame[column]), 1):
        result.append({"segment_id": f"segment_{index:03d}", "label": label, "start_timestamp_sec": frame.iloc[start].timestamp_sec, "end_timestamp_sec": frame.iloc[stop - 1].timestamp_sec, "first_frame_id": int(frame.iloc[start].frame_id), "last_frame_id": int(frame.iloc[stop - 1].frame_id), "frames": stop - start, "confidence": frame.iloc[start:stop].confidence.mean()})
    return result


def apply_overrides(frame, path, destination):
    path = Path(path)
    overrides = pd.read_csv(path).to_dict("records") if path.suffix.lower() == ".csv" else read_json(path)
    if isinstance(overrides, dict):
        overrides = overrides.get("segments", [])
    output = frame.copy()
    changes = []
    allowed = {"GLOBAL", "LOCAL", "APPROACH", "TRANSITION", "UNKNOWN", "TOP_CANDIDATE"}
    for item in overrides:
        label = item["label"]
        if label not in allowed and not label.startswith("LOCAL_"):
            raise ValueError(f"Invalid segment override label {label}")
        selection = output.timestamp_sec.between(float(item["start_timestamp_sec"]), float(item["end_timestamp_sec"]))
        before = output.loc[selection, ["frame_id", "label"]].to_dict("records")
        output.loc[selection, "label"] = label
        output.loc[selection, "confidence"] = float(item.get("confidence", .8))
        output.loc[selection, "label_source"] = item.get("source", "MANUAL_OVERRIDE")
        changes.append({"change": item, "previous": before, "applied_at": now()})
    version = f"manual_{sha256(path)[:12]}"
    write_json(Path(destination) / "versions" / f"{version}.json", {"version": version, "source_path": str(path.resolve()), "sha256": sha256(path), "applied_at": now(), "changes": changes})
    return output, version


def coarse_segment(directory, configuration, force=False, override=None):
    directory = Path(directory)
    output = directory / "segments"
    output.mkdir(exist_ok=True)
    parameters = configuration["segmentation"]
    quality_path = directory / "quality" / "frame_quality.csv"
    inputs = [quality_path] + ([override] if override else [])
    with stage(directory, "segment", parameters, inputs, force) as execute:
        if not execute:
            return pd.read_csv(output / "coarse_frame_labels.csv")
        frame = pd.read_csv(quality_path)
        ratios = np.log(frame.feature_scale_ratio.where(frame.feature_scale_ratio > 0))
        valid = (frame.verified_match_count >= 20) & (frame.scale_ratio_iqr < .7)
        log_scale = ratios.where(valid, 0).fillna(0).clip(-.3, .3)
        cumulative = log_scale.cumsum().rolling(5, center=True, min_periods=1).median()
        frame["relative_scale_state"] = cumulative
        expansion = frame.flow_expansion.fillna(0).rolling(3, center=True, min_periods=1).median()
        changes = log_scale.rolling(3, center=True, min_periods=1).mean()
        labels = np.full(len(frame), "UNKNOWN", dtype=object)
        stable = changes.abs() < parameters["scale_change_threshold"]
        usable = (frame.feature_coverage >= .35) & (frame.feature_count >= 100)
        if len(frame) >= 6:
            reference_candidates = cumulative[stable & usable]
            reference = reference_candidates.quantile(.3) if len(reference_candidates) else cumulative.median()
            spread = cumulative.quantile(.9) - cumulative.quantile(.1)
            labels[stable & usable & (cumulative <= reference + .18)] = "GLOBAL"
            if spread > .25:
                labels[stable & usable & (cumulative >= reference + max(.3, spread * .45))] = "LOCAL"
            approach = (changes > parameters["scale_change_threshold"]) & (expansion > .002) & valid
            labels[approach] = "APPROACH"
            discontinuity = ((frame.verified_match_count < 12) & (frame.image_change_score > frame.image_change_score.quantile(.75))) | (changes < -parameters["scale_change_threshold"])
            labels[discontinuity] = "TRANSITION"
        labels = smooth_labels(labels, parameters["min_run"])
        frame["label"] = labels
        frame["confidence"] = np.where(labels == "UNKNOWN", .15, np.where(labels == "APPROACH", .55, .5))
        frame["label_source"] = "AUTOMATIC_2D_PROXY_NOT_DISTANCE_VERIFIED"
        auto = frame[["video_id", "frame_id", "filename", "timestamp_sec", "label", "confidence", "label_source", "relative_scale_state"]].copy()
        automatic = {"created_at": now(), "algorithm": "verified SIFT scale state + forward-backward LK expansion, relative stable regimes; no fractional video split", "frames": auto.to_dict("records"), "segments": segment_records(auto), "limitations": "GLOBAL/LOCAL are tentative scale/motion candidates, not foreground identification or proof of an orbit."}
        previous_automatic = output / "versions" / "automatic_coarse.json"
        if previous_automatic.exists():
            write_json(output / "versions" / f"automatic_coarse_original_{sha256(previous_automatic)[:12]}.json", read_json(previous_automatic))
        write_json(previous_automatic, automatic)
        version = "automatic_coarse"
        if override:
            auto, version = apply_overrides(auto, override, output)
        auto.to_csv(output / "coarse_frame_labels.csv", index=False)
        write_json(output / "coarse_segments.json", {"version": version, "automatic_version": "automatic_coarse", "segments": segment_records(auto), "frames": auto.to_dict("records")})
        timeline(frame, ["frame_motion_median", "feature_scale_ratio", "relative_scale_state", "feature_match_count"], output / "motion_timeline.png")
        segment_timeline(auto, output / "coarse_segment_timeline.png")
        print(f"SEGMENT {directory.name} {auto.label.value_counts().to_dict()}", flush=True)
        return auto


def refine_segments(directory, cameras, configuration):
    directory = Path(directory)
    coarse = pd.read_csv(directory / "segments" / "coarse_frame_labels.csv")
    extra_columns = [column for column in ["median_shared_global_distance_ratio", "adjacent_sparse_jaccard"] if column in cameras]
    frame = coarse.merge(cameras[["filename", "registered", "median_observed_depth", "median_ray_distance", "camera_center_x", "camera_center_y", "camera_center_z", "observed_points", "viewing_direction"] + extra_columns], on="filename", how="left")
    frame["geometry_validated"] = False
    protected_semantic = frame.label_source.str.startswith("AGNES_API_FRAME_REVIEW")
    frame["refinement_evidence"] = "UNREGISTERED_TEMPORAL_INFERENCE"
    seed = frame[(frame.label == "GLOBAL") & frame.registered & (frame.observed_points >= 30)]
    reference = seed.median_ray_distance.median() if len(seed) >= 5 else np.nan
    if np.isfinite(reference) and reference > 0:
        relative_distance = frame.median_ray_distance / reference
        if "median_shared_global_distance_ratio" in frame:
            relative_distance = frame.median_shared_global_distance_ratio.combine_first(relative_distance)
        frame["relative_observed_distance"] = relative_distance
        near = relative_distance.rolling(5, center=True, min_periods=2).median() < .7
        eligible = frame.registered & (frame.observed_points >= 30)
        retained = eligible & frame.label.eq("GLOBAL") & (relative_distance >= .7)
        frame.loc[retained, "geometry_validated"] = True
        frame.loc[retained, "confidence"] = .7
        frame.loc[retained, "refinement_evidence"] = "REGISTERED_POSE_AND_FULL_SCENE_POINT_DEPTH_PROXY"
        covisibility_supported = frame.adjacent_sparse_jaccard.fillna(0) > .01 if "adjacent_sparse_jaccard" in frame else True
        local = near & eligible & covisibility_supported & ~frame.label.isin(["APPROACH", "TRANSITION"])
        frame.loc[local & ~protected_semantic, "label"] = "LOCAL"
        frame.loc[local, "geometry_validated"] = True
        frame.loc[local, "confidence"] = .7
        frame.loc[local, "refinement_evidence"] = "REGISTERED_COMMON_POINT_RELATIVE_DISTANCE_AND_COVISIBILITY_PROXY"
        derivative = np.log(relative_distance.where(relative_distance > 0)).diff().rolling(3, center=True, min_periods=1).median()
        approach = eligible & (derivative < -.07) & (frame.label != "LOCAL")
        frame.loc[approach & ~protected_semantic, "label"] = "APPROACH"
        frame.loc[approach, "geometry_validated"] = True
        frame.loc[approach, "confidence"] = .65
        frame.loc[approach, "refinement_evidence"] = "DECREASING_OBSERVED_POINT_DISTANCE_PROXY"
    else:
        frame["relative_observed_distance"] = np.nan
    smoothed = smooth_labels(frame.label, configuration["segmentation"]["min_run"])
    frame.loc[~protected_semantic, "label"] = smoothed[~protected_semantic]
    local_number = 0
    for start, stop, label in runs(frame.label):
        if label.startswith("LOCAL"):
            local_number += 1
            frame.loc[frame.index[start:stop], "label"] = f"LOCAL_{local_number:02d}"
    frame["label_version"] = "refined_v1"
    frame.to_csv(directory / "segments" / "segment_confidence.csv", index=False)
    write_json(directory / "segments" / "refined_segments.json", {"version": "refined_v1", "created_at": now(), "segments": segment_records(frame), "frames": frame.to_dict("records"), "limitations": ["Depth is median distance to successfully reconstructed full-scene points; scene-content changes can confound it.", "No semantic plant masks or known gravity: no invented TOP_CANDIDATE.", "Unregistered frames retain 2D/time labels and are not 3D-validated."]})
    segment_timeline(frame, directory / "segments" / "refined_segment_timeline.png")
    return frame
