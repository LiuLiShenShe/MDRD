from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from mdrd.common import read_json, sha256, write_json
from mdrd.video.media import choose_timestamp_indices, parse_showinfo


def sampled_intervals(review):
    intervals = []
    for segment in review["segments"]:
        if segment["label"] in {"LOCAL", "APPROACH", "TRANSITION", "TOP_CANDIDATE"}:
            intervals.append((max(0, segment["start_timestamp_sec"] - .5), segment["end_timestamp_sec"] + .5))
    return intervals


def select_candidates(source_times, original_times, review, rate, maximum=30):
    if rate <= 2:
        raise ValueError("Supplement rate must exceed original 2 fps")
    intervals = sampled_intervals(review)
    requested = []
    for start, end in intervals:
        requested += list(np.arange(start, end + 1e-6, 1 / rate))
    selected = choose_timestamp_indices(source_times, requested)
    extras = [int(index) for index in selected if min(abs(source_times[index] - np.asarray(original_times))) > .07 and any(start <= source_times[index] <= end for start, end in intervals)]
    groups = [[index for index in extras if start <= source_times[index] <= end] for start, end in intervals]
    chosen = []
    while len(chosen) < maximum and any(groups):
        for group in groups:
            if group and len(chosen) < maximum:
                candidate = group.pop(0)
                if candidate not in chosen:
                    chosen.append(candidate)
    return sorted(chosen)


def supplement_video(video_dir, output_dir, review_path, densities=(4., 8.), maximum=24):
    video_dir, output_dir = Path(video_dir), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    review = read_json(review_path)
    if review.get("video_id") != video_dir.name:
        raise ValueError("Segment review does not match source video")
    original = pd.read_csv(video_dir / "frame_manifest.csv")
    source = read_json(video_dir / "extraction_summary.json")["source"]
    source_path = Path(source["source_path"])
    if sha256(source_path) != source["file_sha256"]:
        raise ValueError("Source video SHA-256 changed since Phase 01")
    decoded = parse_showinfo((video_dir / "logs" / "ffmpeg_extract.log").read_text(errors="replace"), "showinfo@source")
    source_times = np.array([row["timestamp_sec"] for row in decoded])
    if not len(source_times) or not np.all(np.diff(source_times) >= 0):
        raise ValueError("Source decoded timestamp log missing or out of order")
    selected = {str(rate): select_candidates(source_times, original.timestamp_sec, review, rate, maximum) for rate in densities}
    union = sorted(set().union(*selected.values()))
    image_dir = output_dir / "frames"
    image_dir.mkdir(exist_ok=True)
    rows = []
    if union:
        frame = cv2.imread(str(video_dir / "sfm_images" / original.filename.iloc[0]))
        width, height = frame.shape[1], frame.shape[0]
        expected = [image_dir / f"extra_{index:06d}.jpg" for index in union]
        if not all(path.exists() for path in expected):
            temporary = output_dir / "decoded"
            temporary.mkdir(exist_ok=True)
            for path in temporary.glob("extra_*.jpg"):
                path.unlink()
            filter_expression = "+".join(f"eq(n\\,{index})" for index in union)
            command = ["ffmpeg", "-hide_banner", "-y", "-threads", "4", "-i", str(source_path), "-map", "0:v:0", "-an", "-sn", "-vf", f"select='{filter_expression}',scale={width}:{height},showinfo@extra", "-fps_mode", "passthrough", "-q:v", "3", str(temporary / "extra_%06d.jpg")]
            start = time.perf_counter()
            with (output_dir / "extraction.log").open("w") as log:
                log.write(json.dumps(command, ensure_ascii=False) + "\n")
                log.flush()
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=900)
            files = sorted(temporary.glob("extra_*.jpg"))
            if result.returncode or len(files) != len(union):
                raise RuntimeError(f"Supplementary FFmpeg extraction failed: {result.returncode}; images={len(files)}/{len(union)}")
            for index, path in zip(union, files):
                path.rename(image_dir / f"extra_{index:06d}.jpg")
            write_json(output_dir / "extraction_receipt.json", {"source_sha256": source["file_sha256"], "command": command, "elapsed_sec": time.perf_counter() - start, "source_frame_indices": union})
        for index in union:
            path = image_dir / f"extra_{index:06d}.jpg"
            image = cv2.imread(str(path))
            if image is None or image.shape[:2] != (height, width):
                raise ValueError(f"Supplement frame dimensions are not camera-compatible: {path}")
            rows.append({"filename": path.name, "image_path": str(path.resolve()), "source_frame_index": index, "timestamp_sec": float(source_times[index]), "file_sha256": sha256(path), "sharpness": float(cv2.Laplacian(cv2.cvtColor(cv2.resize(image, (640, round(height * 640 / width))), cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()), "eligible": True, "scope": "PROVISIONAL_LOCAL_OR_TRANSITION_NOT_HUMAN_CONFIRMED"})
    pd.DataFrame(rows, columns=["filename", "image_path", "source_frame_index", "timestamp_sec", "file_sha256", "sharpness", "eligible", "scope"]).to_csv(output_dir / "candidate_frames.csv", index=False)
    summary = {"video_id": video_dir.name, "source_sha256": source["file_sha256"], "original_2fps_frames": len(original), "densities": {rate: {"source_frame_indices": indices, "extra_frames": len(indices)} for rate, indices in selected.items()}, "unique_extra_frames": len(union), "human_reviewed": bool(review.get("human_ground_truth_available")), "status": "PROVISIONAL_AUTO_SUPPLEMENT_CANDIDATES", "note": "Candidates are real decoded source frames, not confirmed independent target views or plant correspondences"}
    write_json(output_dir / "summary.json", summary)
    return summary
