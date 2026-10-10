from __future__ import annotations

import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from mdrd.common import environment_report, read_json, run_command, sha256, stage, write_json


def discover(root):
    root = Path(root)
    if root.is_file():
        return [root.resolve()] if root.suffix.lower() in {".mov", ".mp4"} else []
    return sorted(path.resolve() for path in root.rglob("*") if path.is_file() and path.suffix.lower() in {".mov", ".mp4"})


def probe(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-select_streams", "v:0", "-show_packets", "-show_entries", "packet=pts,pts_time,dts_time,duration_time,flags", "-of", "json", str(path)], capture_output=True, text=True, check=True)
    metadata = json.loads(result.stdout)
    packets = metadata.get("packets", [])
    times = np.sort([float(packet["pts_time"]) for packet in packets if "pts_time" in packet])
    increments = np.diff(times)
    metadata["timestamp_diagnostics"] = {"source": "ffprobe packet presentation timestamps (not inferred from fps)", "packet_count": len(packets), "distinct_pts_count": len(np.unique(times)), "pts_first": times[0] if len(times) else None, "pts_last": times[-1] if len(times) else None, "pts_delta_min": np.min(increments) if len(increments) else None, "pts_delta_median": np.median(increments) if len(increments) else None, "pts_delta_max": np.max(increments) if len(increments) else None, "distinct_cadence_count": len(np.unique(np.round(increments, 6))), "variable_cadence": len(np.unique(np.round(increments, 6))) > 1, "decoded_frame_count": None}
    return metadata


def inspect(video_root, configuration, force=False):
    output = Path(configuration["output_root"])
    output.mkdir(parents=True, exist_ok=True)
    environment_report(output, configuration["sfm"]["executable"])
    videos = discover(video_root)
    if not videos:
        write_json(output / "video_metadata.json", {"video_root": str(video_root), "videos": [], "status": "BLOCKED_NO_VIDEOS"})
        pd.DataFrame(columns=["video_id", "source_path", "duration_sec"]).to_csv(output / "video_inventory.csv", index=False)
        return []
    records = []
    all_metadata = []
    for index, path in enumerate(videos, 1):
        video_id = f"video_{index:03d}"
        cached = output / "metadata" / f"{video_id}.json"
        stat = path.stat()
        previous = read_json(cached) if cached.exists() else {}
        if not force and previous.get("source_path") == str(path) and previous.get("size_bytes") == stat.st_size and previous.get("mtime_ns") == stat.st_mtime_ns:
            item = previous
        else:
            item = {"video_id": video_id, "source_path": str(path), "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns, "file_sha256": sha256(path), "ffprobe": probe(path)}
            write_json(cached, item)
        metadata = item["ffprobe"]
        stream = metadata["streams"][0]
        rotation = stream.get("tags", {}).get("rotate")
        for data in stream.get("side_data_list", []):
            rotation = data.get("rotation", rotation)
        timestamp_info = metadata["timestamp_diagnostics"]
        records.append({"video_id": video_id, "filename": path.name, "source_path": str(path), "file_sha256": item["file_sha256"], "size_bytes": stat.st_size, "duration_sec": float(metadata["format"]["duration"]), "codec": stream["codec_name"], "width": stream["width"], "height": stream["height"], "pixel_format": stream.get("pix_fmt"), "color_transfer": stream.get("color_transfer"), "avg_frame_rate": stream.get("avg_frame_rate"), "r_frame_rate": stream.get("r_frame_rate"), "time_base": stream.get("time_base"), "declared_frames": stream.get("nb_frames"), "rotation_degrees": rotation or 0, **timestamp_info})
        all_metadata.append(item)
        print(f"INSPECT {video_id} {path.name}", flush=True)
    pd.DataFrame(records).to_csv(output / "video_inventory.csv", index=False)
    write_json(output / "video_metadata.json", {"video_root": str(Path(video_root).resolve()), "videos": all_metadata, "limitations": ["Packet cadence is a VFR diagnostic; decoded extraction log is the frame timestamp authority.", "Electronic stabilization/crop/rolling shutter are not ruled out by locked focus or a nominal 1x lens."]})
    return records


def choose_timestamp_indices(times, requested_times):
    values = np.asarray(times, dtype=float)
    targets = np.asarray(requested_times, dtype=float)
    if not len(values):
        return np.array([], dtype=int)
    if not np.all(np.isfinite(values)) or np.any(np.diff(values) < 0):
        raise ValueError("Presentation timestamps must be finite and sorted")
    right = np.minimum(np.searchsorted(values, targets), len(values) - 1)
    left = np.maximum(right - 1, 0)
    selected = np.where(np.abs(values[left] - targets) <= np.abs(values[right] - targets), left, right)
    return np.unique(selected)


def parse_showinfo(text, marker="showinfo@selected"):
    records = []
    pattern = re.compile(r"n:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:([\d.eE+\-]+).*?s:(\d+)x(\d+)")
    for line in text.splitlines():
        if marker not in line:
            continue
        match = pattern.search(line)
        if match:
            source_index, pts, timestamp, width, height = match.groups()
            records.append({"source_frame_index": int(source_index), "pts": int(pts), "timestamp_sec": float(timestamp), "width": int(width), "height": int(height)})
    return records


def extract(record, configuration, force=False, supplemental_times=None):
    output = Path(configuration["output_root"]) / record["video_id"]
    sampling = configuration["sampling"]
    manifest_path = output / "frame_manifest.csv"
    inputs = [record["source_path"]]
    with stage(output, "extract", {**sampling, "supplemental_times": supplemental_times}, inputs, force) as execute:
        if not execute:
            return pd.read_csv(manifest_path)
        frames = output / "frames"
        frames.mkdir(parents=True, exist_ok=True)
        for stale in frames.glob("frame_*"):
            stale.unlink()
        duration = record["duration_sec"]
        method = "fixed_fps"
        interval = 1.0 / sampling["fps"]
        if sampling.get("interval") is not None:
            interval = float(sampling["interval"])
            method = "fixed_interval"
        if sampling.get("target_count") is not None:
            interval = duration / max(1, int(sampling["target_count"]))
            method = "target_count"
        if sampling.get("max_images") and duration / interval > sampling["max_images"]:
            interval = duration / sampling["max_images"]
            method += "_max_images_capped"
        if interval <= 0:
            raise ValueError("Sampling interval must be positive")
        expression = f"isnan(prev_selected_t)+gte(t-prev_selected_t,{interval:.9f})"
        if sampling.get("target_count") is not None and not supplemental_times:
            result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames", "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", record["source_path"]], capture_output=True, text=True, check=True)
            decoded = json.loads(result.stdout)["frames"]
            times = [float(item["best_effort_timestamp_time"]) for item in decoded]
            count = int(sampling["target_count"])
            if sampling.get("max_images"):
                count = min(count, int(sampling["max_images"]))
            if count < 1 or count > len(times):
                raise ValueError("Target count must be between one and the decoded frame count")
            selected = choose_timestamp_indices(times, np.linspace(times[0], times[-1], count))
            expression = "+".join(f"eq(n,{index})" for index in selected)
            write_json(output / "target_count_timestamp_selection.json", {"actual_decoded_times": times, "selected_source_indices": selected.tolist()})
        if supplemental_times:
            old_log = output / "logs" / "ffmpeg_extract.log"
            if not manifest_path.exists() or not old_log.exists():
                raise ValueError("Adaptive supplementation requires an existing uniform manifest and decoded source PTS log")
            previous_manifest = pd.read_csv(manifest_path)
            decoded = parse_showinfo(old_log.read_text(errors="replace"), "showinfo@source")
            selected_indices = set(previous_manifest.source_frame_index.astype(int))
            nearest = choose_timestamp_indices([item["timestamp_sec"] for item in decoded], supplemental_times)
            selected_indices.update(decoded[index]["source_frame_index"] for index in nearest)
            expression = "+".join(f"eq(n,{index})" for index in sorted(selected_indices))
            method += "_adaptive_supplement"
        filters = ["showinfo@source", f"select='{expression}'"]
        if sampling.get("max_dimension"):
            maximum = int(sampling["max_dimension"])
            filters.append(f"scale='if(gte(iw,ih),min(iw,{maximum}),-2)':'if(gte(iw,ih),-2,min(ih,{maximum}))'")
        filters.append("showinfo@selected")
        log = output / "logs" / "ffmpeg_extract.log"
        command = ["ffmpeg", "-hide_banner", "-y", "-threads", "4", "-copyts", "-i", record["source_path"], "-map", "0:v:0", "-an", "-sn", "-vf", ",".join(filters), "-fps_mode", "passthrough", "-threads", "2"]
        if sampling["format"] in {"jpg", "jpeg"}:
            command += ["-q:v", "2"]
        command += [str(frames / f"frame_%06d.{sampling['format']}")]
        run_command(command, log)
        text = log.read_text(errors="replace")
        selected = parse_showinfo(text)
        source = parse_showinfo(text, "showinfo@source")
        source_by_pts = {item["pts"]: item["source_frame_index"] for item in source}
        paths = sorted(frames.glob("frame_*"))
        if len(paths) != len(selected) or not paths:
            raise RuntimeError(f"PTS/frame mismatch: {len(selected)} selected, {len(paths)} files")
        rows = []
        for index, (path, timestamp) in enumerate(zip(paths, selected), 1):
            rows.append({"video_id": record["video_id"], "frame_id": index, **timestamp, "source_frame_index": source_by_pts[timestamp["pts"]], "image_path": str(path.resolve()), "filename": path.name, "sampling_method": method, "sampling_interval_requested": interval, "file_sha256": sha256(path), "source_sha256": record["file_sha256"], "source_time_base": record["time_base"], "rotation_applied_by_ffmpeg": True})
        manifest = pd.DataFrame(rows)
        if manifest.timestamp_sec.duplicated().any() or np.any(np.diff(manifest.timestamp_sec) <= 0):
            raise RuntimeError("Extracted frames have invalid or duplicate PTS")
        manifest.to_csv(manifest_path, index=False)
        write_json(output / "extraction_summary.json", {"decoded_frame_count": len(source), "extracted_frames": len(rows), "source": record, "sampling": sampling, "actual_pts_delta": np.diff(manifest.timestamp_sec).tolist(), "image_orientation": "FFmpeg autorotate; dimensions after filtering", "color_note": "8-bit OpenCV analysis; no HDR radiometric calibration or tone-map claim"})
        print(f"EXTRACT {record['video_id']} {len(rows)} frames", flush=True)
        return manifest


def preview_inventory(records, configuration, count=10):
    from mdrd.quality.metrics import image_metrics
    from mdrd.visualization.plots import contact_sheet

    output = Path(configuration["output_root"])

    def process(record):
        directory = output / "previews" / record["video_id"]
        directory.mkdir(parents=True, exist_ok=True)
        times = np.linspace(0, record["duration_sec"] - .15, count)
        rows = []
        previous = None
        motions = []
        for index, timestamp in enumerate(times):
            path = directory / f"preview_{index:02d}.jpg"
            if not path.exists():
                run_command(["ffmpeg", "-hide_banner", "-loglevel", "warning", "-y", "-threads", "2", "-ss", str(timestamp), "-i", record["source_path"], "-frames:v", "1", "-vf", "scale=720:-2", "-threads", "1", str(path)], directory / f"seek_{index:02d}.log")
            image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            metrics, _, _ = image_metrics(image, 720, 700)
            if previous is not None:
                corners = cv2.goodFeaturesToTrack(previous, 300, .01, 10)
                if corners is not None:
                    tracked, status, _ = cv2.calcOpticalFlowPyrLK(previous, image, corners, None)
                    valid = status.ravel() == 1
                    motions.append(float(np.median(np.linalg.norm(tracked[valid] - corners[valid], axis=2))))
            rows.append({"image_path": str(path), "timestamp_sec": timestamp, **metrics})
            previous = image
        frame = pd.DataFrame(rows)
        frame.to_csv(directory / "preview_quality.csv", index=False)
        contact_sheet(frame, directory / "contact_sheet.jpg", title=record["video_id"], columns=5)
        print(f"PREVIEW {record['video_id']}", flush=True)
        return {"video_id": record["video_id"], "duration_sec": record["duration_sec"], "laplacian_median": frame.laplacian_variance.median(), "laplacian_p10": frame.laplacian_variance.quantile(.1), "sharpness_variation": frame.laplacian_variance.std() / max(frame.laplacian_variance.mean(), 1e-9), "feature_median": frame.feature_count.median(), "motion_median_px": np.median(motions) if motions else None, "motion_variation": np.std(motions) / max(np.mean(motions), 1e-9) if motions else None, "sampling": "10 approximate seek preview times; not analysis frame manifest"}

    with ThreadPoolExecutor(max_workers=3) as pool:
        summaries = list(pool.map(process, records))
    summary = pd.DataFrame(summaries)
    summary.to_csv(output / "preview_inventory.csv", index=False)
    return summary
