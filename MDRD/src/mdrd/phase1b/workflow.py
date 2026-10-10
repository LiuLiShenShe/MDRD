from __future__ import annotations

from pathlib import Path

from mdrd.common import read_json, sha256, write_json


def run_phase1b(command, output, selected, args):
    root = Path(output) / "phase1b"
    if command == "phase1b-report":
        from mdrd.phase1b.report import make_reports

        return make_reports(output, selected)
    if command == "foreground":
        from mdrd.phase1b.foreground import analyze_foreground, make_sam_candidate

        for video in selected:
            folder = root / "foreground" / video
            proposals = folder / "prompt_proposals.json"
            manifest = args.override or folder / "mask_manifest.json"
            if args.checkpoint and proposals.exists() and not args.override:
                prompts = read_json(proposals)["prompts"]
                rows = [make_sam_candidate(row["image_path"], row, args.checkpoint, folder / "masks" / f"{row['filename']}.png") for row in prompts if row["status"] == "PROVISIONAL_AUTO"]
                write_json(manifest, {"video_id": video, "source": "PROVISIONAL_AUTO_NOT_HUMAN", "checkpoint_sha256": sha256(args.checkpoint), "masks": rows})
            if not Path(manifest).exists():
                write_json(manifest, {"video_id": video, "source": "NONE_ALL_UNCERTAIN", "masks": [], "status": "BLOCKED_NO_PLANT_MASK_OR_PROMPTS"})
            analyze_foreground(Path(output) / video, folder, manifest)
        return
    if command == "supplement":
        from mdrd.phase1b.supplement import supplement_video

        if any(video != "video_008" for video in selected) and not (root / "supplementation" / "video_008" / "summary.json").exists():
            raise ValueError("Run video_008 supplementation before the other samples")
        for video in selected:
            supplement_video(Path(output) / video, root / "supplementation" / video, root / "segment_review" / video / "reviewed_segments.json", densities=args.densities or (4., 8.))
        return
    if command == "ablate-registration":
        from mdrd.phase1b.ablation import ablate_video

        if any(video != "video_008" for video in selected) and not (root / "ablations" / "video_008" / "M2" / "result.json").exists():
            raise ValueError("Run video_008 controlled registration ablation before other samples")
        for video in selected:
            ablate_video(Path(output) / video, root / "ablations" / video, root / "supplementation" / video)
        return
    if command == "evidence":
        from mdrd.phase1b.evidence import analyze_evidence

        for video in selected:
            analyze_evidence(Path(output) / video, root / "geometric_evidence" / video / "M0")
        return
    raise ValueError(f"Unsupported Phase 1B command: {command}")
