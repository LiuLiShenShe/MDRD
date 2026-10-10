from __future__ import annotations

import json
import html
import subprocess
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from mdrd.common import now, read_json, sha256, write_json


def _visual_review_rows(path):
    path = Path(path)
    if not path.exists():
        return {}
    payload = read_json(path)
    return {int(item["frame_id"]): dict(item) for item in payload.get("segments", []) if item.get("frame_id") is not None}


def _runs(labels):
    values = list(labels)
    if not values:
        return []
    starts = [0] + [i for i in range(1, len(values)) if values[i] != values[i - 1]]
    stops = starts[1:] + [len(values)]
    return [(start, stop, values[start]) for start, stop in zip(starts, stops)]


def _frame_table(video_dir):
    video_dir = Path(video_dir)
    manifest = pd.read_csv(video_dir / "frame_manifest.csv")
    quality = pd.read_csv(video_dir / "quality" / "frame_quality.csv")
    refined = pd.read_csv(video_dir / "segments" / "segment_confidence.csv")
    table = manifest.merge(quality[["filename", "quality_label", "laplacian_variance", "feature_count", "feature_coverage"]], on="filename", how="left")
    table = table.merge(refined[["filename", "label", "confidence", "label_source", "geometry_validated"]], on="filename", how="left")
    cameras_path = video_dir / "geometry" / "cameras.csv"
    if cameras_path.exists():
        cameras = pd.read_csv(cameras_path)
        columns = [c for c in ["filename", "registered", "observed_points", "segment_confidence"] if c in cameras]
        table = table.merge(cameras[columns], on="filename", how="left")
    else:
        table["registered"] = False
        table["observed_points"] = 0
    audit_path = video_dir / "sfm" / "registration_audit.csv"
    if audit_path.exists():
        audit = pd.read_csv(audit_path)
        columns = [c for c in ["filename", "registration_status", "failure_reason"] if c in audit]
        table = table.merge(audit[columns], on="filename", how="left")
    return table


def _contact_sheet(table, output_path, title):
    columns = 6
    rows = max(1, int(np.ceil(len(table) / columns)))
    figure, axes = plt.subplots(rows, columns, figsize=(columns * 2.8, rows * 2.35), squeeze=False)
    for axis in axes.ravel():
        axis.axis("off")
    colors = {"GLOBAL": "#1f77b4", "APPROACH": "#ff7f0e", "LOCAL": "#d62728", "TOP_CANDIDATE": "#9467bd", "TRANSITION": "#8c564b", "UNKNOWN": "#7f7f7f"}
    for axis, item in zip(axes.ravel(), table.to_dict("records")):
        image = cv2.imread(str(item["preview_path"]))
        if image is None:
            continue
        axis.imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        candidate = str(item.get("candidate_label", "UNKNOWN"))
        broad = "LOCAL" if candidate.startswith("LOCAL") else candidate
        registered = "R" if bool(item.get("registered", False)) else "-"
        quality = str(item.get("quality_label", "N/A"))
        axis.set_title(f"src {int(item['source_frame_index'])} t={float(item['timestamp_sec']):.2f}s\n{candidate} [{registered}] {quality} pts={int(item.get('observed_points') or 0)}", fontsize=7, color=colors.get(broad, "black"))
    figure.suptitle(title, fontsize=13)
    figure.tight_layout(rect=[0, 0, 1, .985])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=110)
    plt.close(figure)


def _timeline(table, output_path, video_id):
    labels = list(dict.fromkeys(table["candidate_label"].astype(str)))
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cards, frames, buttons = [], [], []
    for index, item in enumerate(table.to_dict("records")):
        preview = html.escape(str(Path("previews") / Path(item["preview_path"]).name), quote=True)
        caption = html.escape(f"{item['timestamp_sec']:.2f}s / source {int(item['source_frame_index'])} / {item['candidate_label']} / {'registered' if item['registered'] else 'unregistered'} / {item['quality_label']} / points {int(item.get('observed_points') or 0)}")
        label = html.escape(str(item["candidate_label"]), quote=True)
        color = "#c64c4c" if label.startswith("LOCAL") else "#eac05b" if label in {"APPROACH", "TRANSITION"} else "#97b3d5"
        cards.append(f'<figure data-label="{label}"><button onclick="showFrame({index})">{caption}</button><a href="{preview}" target="_blank"><img loading="lazy" src="{preview}" alt="{caption}"></a></figure>')
        buttons.append(f'<button style="background:{color}" title="{caption}" onclick="showFrame({index})">{float(item["timestamp_sec"]):.1f}</button>')
        frames.append({"preview": str(Path("previews") / Path(item["preview_path"]).name), "caption": html.unescape(caption)})
    options = '<option value="">ALL stages</option>' + "".join(f'<option>{html.escape(label)}</option>' for label in labels)
    payload = json.dumps(frames, ensure_ascii=False).replace("<", "\\u003c")
    script = 'const frames=' + payload + ';function showFrame(index){document.getElementById("seek").value=index;document.getElementById("activeImage").src=frames[index].preview;document.getElementById("activeCaption").textContent=frames[index].caption;}function filterStage(label){document.querySelectorAll("figure[data-label]").forEach(card=>{card.hidden=Boolean(label&&card.dataset.label!==label);});}showFrame(0);'
    document = '<!doctype html><html><head><meta charset="utf-8"><title>Segment review</title><style>body{font:14px sans-serif;margin:1em}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px}figure{margin:0;padding:5px;border:1px solid #aaa}img{width:100%}button{cursor:pointer;font:inherit}.bar{display:flex;overflow:auto}.bar button{min-width:42px}.active{max-width:620px}#seek{width:100%}</style></head><body><h1>' + html.escape(video_id) + ': complete-duration provisional review</h1><p>Automated labels, NOT human truth. Click a timestamp or drag the slider. All images below are exact source decoded-frame indices.</p><div class="bar">' + "".join(buttons) + '</div><input id="seek" type="range" min="0" max="' + str(max(0, len(frames) - 1)) + '" value="0" step="1" oninput="showFrame(Number(this.value))"><div class="active"><img id="activeImage" alt="Selected source frame"><p id="activeCaption"></p></div><h2>Source previews in time order</h2><select onchange="filterStage(this.value)">' + options + '</select><div class="grid">' + "".join(cards) + '</div><script>' + script + '</script></body></html>'
    Path(output_path).write_text(document, encoding="utf-8")


def _source_previews(table, source_path, destination):
    destination.mkdir(parents=True, exist_ok=True)
    receipt_path = destination.parent / "source_preview_receipt.json"
    source_hash = sha256(source_path)
    indices = [int(value) for value in table.source_frame_index]
    expected = len(indices)
    existing = sorted(destination.glob("preview_[0-9][0-9][0-9][0-9].jpg"))
    receipt = read_json(receipt_path) if receipt_path.exists() else {}
    if not (receipt.get("source_sha256") == source_hash and receipt.get("source_frame_indices") == indices and len(existing) == expected):
        for old in existing:
            old.unlink()
        expression = "+".join(f"eq(n\\,{index})" for index in indices)
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source_path), "-map", "0:v:0", "-an", "-sn", "-vf", f"select='{expression}',scale=480:-2", "-fps_mode", "passthrough", "-q:v", "5", str(destination / "preview_%04d.jpg")]
        result = subprocess.run(command, capture_output=True, text=True, timeout=600)
        if result.returncode:
            raise RuntimeError(f"Source preview decode failed: {result.stderr[-2000:]}")
        existing = sorted(destination.glob("preview_[0-9][0-9][0-9][0-9].jpg"))
        if len(existing) != expected:
            raise RuntimeError(f"Source preview does not cover complete video: {len(existing)}/{expected}")
        write_json(receipt_path, {"source_path": str(source_path), "source_sha256": source_hash, "command": command, "preview_count": len(existing), "source_frame_indices": indices, "source_timestamps_sec": table.timestamp_sec.tolist(), "sampling": "source MOV redecoded at exact 2 fps decoded indices with FFmpeg autorotate, not resized cached SfM images"})
    return existing


def review_video(video_dir, phase_root):
    video_dir = Path(video_dir)
    phase_root = Path(phase_root)
    video_id = video_dir.name
    output = phase_root / "segment_review" / video_id
    output.mkdir(parents=True, exist_ok=True)
    table = _frame_table(video_dir)
    source = read_json(video_dir / "extraction_summary.json")["source"]["source_path"]
    previews = _source_previews(table, source, output / "previews")
    table["preview_path"] = [str(path) for path in previews]
    visual = _visual_review_rows(video_dir / "segments" / "visual_review_overrides.json")
    candidates, sources, descriptions = [], [], []
    for item in table.to_dict("records"):
        review = visual.get(int(item["frame_id"]))
        if review:
            candidates.append(str(review.get("label", "UNKNOWN")))
            sources.append(str(review.get("source", "AUTOMATED_VISUAL_REVIEW")))
            descriptions.append(str(review.get("description", "")))
        else:
            candidates.append(str(item.get("label", "UNKNOWN")))
            sources.append("IMAGE_AUTO_FALLBACK")
            descriptions.append("")
    table["auto_label"] = table["label"].fillna("UNKNOWN")
    table["candidate_label"] = candidates
    table["candidate_source"] = sources
    table["candidate_description"] = descriptions
    table["human_confirmed"] = False
    table["review_status"] = "PROVISIONAL_AUTO_REVIEW_PENDING_HUMAN"
    reviewed_path = output / "reviewed_segments.json"
    if reviewed_path.exists() and read_json(reviewed_path).get("human_ground_truth_available"):
        raise ValueError(f"Human-reviewed segments must not be overwritten: {reviewed_path}")
    table.to_csv(output / "original_vs_candidate_labels.csv", index=False)
    _contact_sheet(table, output / "contact_sheet.png", f"{video_id}: complete 2 fps audit coverage (provisional)")
    _timeline(table, output / "timeline.html", video_id)
    table[["frame_id", "timestamp_sec", "source_frame_index", "filename", "preview_path", "auto_label", "candidate_label", "candidate_source", "registered", "quality_label", "laplacian_variance", "observed_points"]].to_csv(output / "contact_sheet_index.csv", index=False)
    records = []
    for index, (start, stop, label) in enumerate(_runs(table["candidate_label"]), 1):
        block = table.iloc[start:stop]
        broad = "LOCAL" if str(label).startswith("LOCAL") else str(label)
        records.append({"segment_id": f"review_segment_{index:03d}", "label": broad, "start_timestamp_sec": float(block.timestamp_sec.iloc[0]), "end_timestamp_sec": float(block.timestamp_sec.iloc[-1]), "frame_ids": [int(value) for value in block.frame_id], "frames": len(block), "source": "PROVISIONAL_AUTO", "source_detail": str(block.candidate_source.iloc[0]), "confidence": None, "human_confirmed": False, "evidence": {"contact_sheet": "contact_sheet.png", "timeline": "timeline.html", "frame_ids": [int(value) for value in block.frame_id]}})
    review_payload = {"video_id": video_id, "created_at": now(), "status": "PROVISIONAL_AUTO_REVIEW_PENDING_HUMAN", "human_ground_truth_available": False, "segments": records, "limitations": ["Labels are derived from automated image-content review and existing 2 fps frame sequence, not human ground truth.", "LOCAL is a visual framing candidate, not a metric distance or same-leaf identity.", "Precision/recall/F1 are intentionally not computed without independent human labels."]}
    write_json(reviewed_path, review_payload)
    short_local = [segment for segment in records if segment["label"] == "LOCAL" and segment["frames"] < 4]
    suspected = [segment for segment in records if segment["label"] in {"APPROACH", "LOCAL", "TOP_CANDIDATE", "TRANSITION"}]
    instructions = [f"# {video_id} segment review instructions", "", "This is a provisional automated review package. It is not a human annotation and must not be used as ground truth without review.", "", "## Review actions", "1. Open `timeline.html` and inspect every candidate APPROACH/LOCAL/TRANSITION interval.", "2. Use `contact_sheet.png` to verify whether the plant body, pot, and target leaves are visible.", "3. If correcting labels, create a separate JSON/CSV override with `source=HUMAN_VERIFIED`, `human_confirmed=true`, and a reviewer identifier.", "4. Do not delete the provisional files.", "", "## Candidate intervals", ""]
    instructions += [f"- `{segment['segment_id']}`: {segment['label']} {segment['start_timestamp_sec']:.3f}–{segment['end_timestamp_sec']:.3f}s, {segment['frames']} frames, source `{segment['source_detail']}`" for segment in suspected]
    instructions += ["", "## Short local candidates", ""] + [f"- {segment['segment_id']}: {segment['frames']} frames; shortness is preserved and is not evidence of omission." for segment in short_local]
    (output / "review_instructions.md").write_text("\n".join(instructions) + "\n", encoding="utf-8")
    local_mask = table.candidate_label.astype(str).str.startswith("LOCAL")
    local_spans = [{"start": segment["start_timestamp_sec"], "end": segment["end_timestamp_sec"], "frames": segment["frames"]} for segment in records if segment["label"] == "LOCAL"]
    return {"video_id": video_id, "frames": len(table), "duration_sec": float(table.timestamp_sec.max()), "auto_local_frames": int(local_mask.sum()), "auto_local_sampled_duration_sec": float(sum(segment["frames"] * .5 for segment in local_spans)), "candidate_local_intervals": json.dumps(local_spans), "candidate_segments": len(records), "short_local_segments": len(short_local), "human_confirmed": False, "output": str(output)}


def review_selected(output_root, sample_ids):
    output_root = Path(output_root)
    summaries = [review_video(output_root / video_id, output_root / "phase1b") for video_id in sample_ids]
    destination = output_root / "phase1b" / "segment_review" / "segment_validation_summary.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summaries).to_csv(destination, index=False)
    return summaries
