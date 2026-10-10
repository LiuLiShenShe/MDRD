from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from mdrd.common import load_config, read_json, sha256, write_json
from mdrd.phase1b.evidence import align_models, analyze_evidence
from mdrd.sfm.pipeline import run_sfm


def fixed_frames(video_dir):
    labels = pd.read_csv(Path(video_dir) / "segments" / "coarse_frame_labels.csv")
    global_names = labels.loc[labels.label == "GLOBAL", "filename"].tolist()
    indices = np.unique(np.r_[np.linspace(0, len(global_names) - 1, min(18, len(global_names)), dtype=int), np.arange(max(0, len(global_names) - 10), len(global_names))])
    return {"GLOBAL": [global_names[index] for index in indices], "LOCAL": labels.loc[labels.label.astype(str).str.startswith("LOCAL"), "filename"].tolist(), "APPROACH": labels.loc[labels.label.isin(["APPROACH", "TRANSITION"]), "filename"].tolist()}


def full_global_frames(video_dir):
    labels = pd.read_csv(Path(video_dir) / "segments" / "coarse_frame_labels.csv")
    return {"GLOBAL": labels.loc[labels.label == "GLOBAL", "filename"].tolist(), "LOCAL": labels.loc[labels.label.astype(str).str.startswith("LOCAL"), "filename"].tolist(), "APPROACH": labels.loc[labels.label.isin(["APPROACH", "TRANSITION"]), "filename"].tolist()}


def adaptive_extra(candidates, excluded_intervals=(), count=10):
    if not len(candidates):
        return []
    values = candidates[~candidates.timestamp_sec.apply(lambda timestamp: any(start <= timestamp <= end for start, end in excluded_intervals))].sort_values("timestamp_sec").copy()
    if not len(values):
        return []
    times = values.timestamp_sec.to_numpy()
    buckets = np.rint(times / 2).astype(int)
    selected = []
    for _, group in values.groupby(buckets):
        selected.append(group.sort_values("sharpness", ascending=False).iloc[0].filename)
    if len(selected) > count:
        indices = np.linspace(0, len(selected) - 1, count, dtype=int)
        selected = [selected[index] for index in indices]
    return selected


def experiment_images(video_dir, supplement_dir, output_dir, phase, fixed):
    video_dir, supplement_dir, output_dir = Path(video_dir), Path(supplement_dir), Path(output_dir)
    if output_dir.exists() and (output_dir / "experiment_configuration.json").exists():
        old = read_json(output_dir / "experiment_configuration.json")
        if old["phase"] != phase or old["fixed"] != fixed:
            raise ValueError("Experiment output already belongs to a different input set")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(video_dir / "frame_manifest.csv")
    original_labels = pd.read_csv(video_dir / "segments" / "coarse_frame_labels.csv")
    names = fixed["GLOBAL"] + fixed["LOCAL"] + (fixed["APPROACH"] if phase in {"M2", "M3"} else [])
    base = manifest[manifest.filename.isin(names)].copy()
    labels = original_labels[original_labels.filename.isin(names)].copy()
    extra_names = []
    if phase == "M3":
        candidates = pd.read_csv(supplement_dir / "candidate_frames.csv")
        reviewed = read_json(supplement_dir.parent.parent / "segment_review" / video_dir.name / "reviewed_segments.json")
        excluded = [(segment["start_timestamp_sec"], segment["end_timestamp_sec"]) for segment in reviewed["segments"] if segment["label"] == "LOCAL"]
        extra_names = adaptive_extra(candidates, excluded)
        additions = candidates[candidates.filename.isin(extra_names)].copy()
        if len(additions):
            additions["video_id"] = video_dir.name
            additions["frame_id"] = range(len(manifest) + 1, len(manifest) + 1 + len(additions))
            base = pd.concat([base, additions], ignore_index=True)
            new_labels = additions[["video_id", "frame_id", "filename", "timestamp_sec"]].copy()
            new_labels["label"] = "APPROACH"
            new_labels["confidence"] = np.nan
            new_labels["label_source"] = "PROVISIONAL_AUTO_SUPPLEMENT_NOT_HUMAN"
            labels = pd.concat([labels, new_labels], ignore_index=True)
    base = base.sort_values("timestamp_sec").reset_index(drop=True)
    labels = labels.sort_values("timestamp_sec").reset_index(drop=True)
    base.to_csv(output_dir / "frame_manifest.csv", index=False)
    segments = output_dir / "segments"
    segments.mkdir(exist_ok=True)
    labels.to_csv(segments / "coarse_frame_labels.csv", index=False)
    quality = pd.read_csv(video_dir / "quality" / "frame_quality.csv")
    quality = quality[quality.filename.isin(names)].copy()
    for row in base[base.filename.isin(extra_names)].to_dict("records"):
        quality = pd.concat([quality, pd.DataFrame([{"filename": row["filename"], "quality_label": "UNASSESSED_SUPPLEMENT", "feature_count": 0, "feature_coverage": 0.}])], ignore_index=True)
    quality_dir = output_dir / "quality"
    quality_dir.mkdir(exist_ok=True)
    quality.to_csv(quality_dir / "frame_quality.csv", index=False)
    policy = {"phase": phase, "fixed": fixed, "base_images": len(names), "extra_images": extra_names, "all_images": base.filename.tolist(), "images": [{"filename": row["filename"], "sha256": row["file_sha256"], "timestamp_sec": row["timestamp_sec"]} for row in base.to_dict("records")], "scope": "Same original GLOBAL/LOCAL target frames for M1/M2/M3; M2 adds original approach, M3 additionally selected source-video transition frames"}
    write_json(output_dir / "experiment_configuration.json", policy)
    return policy


def ablate_video(video_dir, root, supplement_dir, phases=("M1", "M2", "M3")):
    video_dir, root = Path(video_dir), Path(root)
    root.mkdir(parents=True, exist_ok=True)
    fixed = fixed_frames(video_dir)
    write_json(root / "fixed_target_images.json", fixed)
    baseline_path = video_dir / "sfm" / "final"
    baseline = read_json(video_dir / "sfm" / "sfm_summary.json")
    write_json(root / "M0" / "result.json", {"phase": "M0", "status": "VALIDATED_EXISTING_PHASE01_NOT_RERUN", "model_path": baseline["model_path"], "registered": baseline["final_model"]["registered_images"], "matching_strategy": baseline["matching_strategy"], "camera_model": baseline["final_model"]["cameras"][0]["model"], "model_sha256": {name: sha256(baseline_path / f"{name}.bin") for name in ("cameras", "images", "points3D")}})
    results = {}
    for phase in phases:
        output_dir = root / phase
        policy = experiment_images(video_dir, supplement_dir, output_dir, phase, fixed)
        parameters = load_config(overrides={"output_root": str(output_dir.parent), "sfm": {"threads": 8, "command_timeout_sec": 240}})
        started = time.perf_counter()
        try:
            sfm = run_sfm(output_dir, parameters)
            from mdrd.phase1b.models import audit_models

            candidate_audit = audit_models(output_dir, output_dir / "model_audit")
            elapsed = time.perf_counter() - started
            registered = set(sfm.get("final_model", {}).get("registered_filenames", []))
            alignment = align_models(sfm["model_path"], baseline["model_path"]) if sfm.get("model_path") else None
            evidence = analyze_evidence(output_dir, output_dir / "evidence") if sfm.get("model_path") else None
            result = {"phase": phase, "status": "EXECUTED" if sfm.get("model_path") else "FAILED_NO_MODEL", "input_count": len(policy["all_images"]), "fixed_global_count": len(fixed["GLOBAL"]), "fixed_local_registered": len(registered & set(fixed["LOCAL"])), "fixed_local_total": len(fixed["LOCAL"]), "registered": len(registered), "raw_tracks": sfm.get("final_model", {}).get("num_3d_points") if sfm.get("final_model") else None, "model_path": sfm.get("model_path"), "matching_strategy": sfm.get("matching_strategy"), "alignment_to_M0": alignment, "full_scene_evidence": evidence, "candidate_models": candidate_audit["count"], "elapsed_sec": elapsed, "foreground_verified": False, "foreground_tracks": None, "note": "Input subset is not comparable to full Phase 01 M0 as a causal matching ablation"}
        except Exception as exception:
            result = {"phase": phase, "status": "FAILED", "error": f"{type(exception).__name__}: {exception}", "elapsed_sec": time.perf_counter() - started, "input_count": len(policy["all_images"])}
        write_json(output_dir / "result.json", result)
        results[phase] = result
    m4 = {"phase": "M4", "status": "BLOCKED", "reason": "No human-verified same-plant surface overlap pairs; deep matching comparison cannot support causal cross-scale conclusion", "target_local_frames": fixed["LOCAL"]}
    write_json(root / "M4" / "result.json", m4)
    return results


def run_full_global_no_bridge_control(video_dir, output_dir, supplement_dir):
    video_dir, output_dir = Path(video_dir), Path(output_dir)
    fixed = full_global_frames(video_dir)
    policy = experiment_images(video_dir, supplement_dir, output_dir, "FULL_GLOBAL_M1", fixed)
    parameters = load_config(overrides={"output_root": str(output_dir.parent), "sfm": {"threads": 8, "command_timeout_sec": 240}})
    started = time.perf_counter()
    sfm = run_sfm(output_dir, parameters)
    result = {"phase": "FULL_GLOBAL_M1", "status": "EXECUTED" if sfm.get("model_path") else "FAILED_NO_MODEL", "input_count": len(policy["all_images"]), "fixed_global_count": len(fixed["GLOBAL"]), "fixed_local_total": len(fixed["LOCAL"]), "fixed_local_registered": len(set(sfm.get("final_model", {}).get("registered_filenames", [])) & set(fixed["LOCAL"])), "registered": sfm.get("final_model", {}).get("registered_images"), "raw_tracks": sfm.get("final_model", {}).get("num_3d_points"), "model_path": sfm.get("model_path"), "elapsed_sec": time.perf_counter() - started, "note": "Diagnostic full-GLOBAL no-bridge control; independent of M1-M3 sparse-global ablations; not a new matching method"}
    write_json(output_dir / "result.json", result)
    return result
