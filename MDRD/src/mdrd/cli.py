from __future__ import annotations

import argparse
import traceback
from pathlib import Path

import pandas as pd

from mdrd.common import load_config, read_json, write_json


def parser():
    argument_parser = argparse.ArgumentParser(description="Traceable Mixed-Distance Reconstruction Diagnostics")
    subparsers = argument_parser.add_subparsers(dest="command", required=True)
    for command in ["inspect", "extract", "quality", "segment", "sfm", "analyze", "report", "run-all", "review-segments", "foreground", "supplement", "ablate-registration", "evidence", "phase1b-report"]:
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--config")
        subparser.add_argument("--input", type=Path)
        subparser.add_argument("--video", type=Path)
        subparser.add_argument("--samples", nargs="+")
        subparser.add_argument("--output", type=Path)
        subparser.add_argument("--fps", type=float)
        subparser.add_argument("--interval", type=float)
        subparser.add_argument("--target-count", type=int)
        subparser.add_argument("--max-images", type=int)
        subparser.add_argument("--format", choices=["png", "jpg", "jpeg"])
        subparser.add_argument("--colmap")
        subparser.add_argument("--camera-model")
        subparser.add_argument("--force", action="store_true")
        subparser.add_argument("--rerun-stage", nargs="*", default=[])
        subparser.add_argument("--no-reuse", action="store_true")
        subparser.add_argument("--preview", action="store_true")
        subparser.add_argument("--override", type=Path)
        subparser.add_argument("--supplemental-times", type=Path)
        subparser.add_argument("--checkpoint", type=Path)
        subparser.add_argument("--densities", nargs="+", type=float)
    return argument_parser


def main(argv=None):
    args = parser().parse_args(argv)
    overrides = {"project_root": str(Path.cwd())}
    if args.output:
        overrides["output_root"] = str(args.output.resolve())
    overrides["sampling"] = {key: getattr(args, key) for key in ["fps", "interval", "target_count", "max_images", "format"] if getattr(args, key) is not None}
    overrides["sfm"] = {}
    if args.colmap:
        overrides["sfm"]["executable"] = args.colmap
    if args.camera_model:
        overrides["sfm"]["camera_model"] = args.camera_model
    configuration = load_config(args.config, overrides)
    output = Path(configuration["output_root"])
    output.mkdir(parents=True, exist_ok=True)
    phase1b_commands = {"review-segments", "foreground", "supplement", "ablate-registration", "evidence", "phase1b-report"}
    if args.command not in phase1b_commands:
        write_json(output / "last_run_configuration.json", configuration)
    if args.command in phase1b_commands:
        selected = args.samples
        if not selected and (output / "selection.json").exists():
            selected = read_json(output / "selection.json")["selected_video_ids"]
        if not selected:
            raise SystemExit("Use --samples for Phase 1B")
        if args.command == "review-segments":
            from mdrd.phase1b.review import review_selected
            review_selected(output, selected)
        else:
            from mdrd.phase1b.workflow import run_phase1b
            run_phase1b(args.command, output, selected, args)
        return 0
    from mdrd.video import discover, extract, inspect, preview_inventory

    video_root = args.video or args.input or configuration.get("video_root")
    if not video_root:
        candidates = discover(configuration["project_root"])
        video_root = Path(configuration["project_root"]) if candidates else None
    if args.command == "inspect" or not (output / "video_inventory.csv").exists():
        if not video_root:
            raise SystemExit("BLOCKED: no videos found; provide --input VIDEO_ROOT")
        records = inspect(video_root, configuration, args.force)
        if args.preview and records:
            preview_inventory(records, configuration)
        if args.command == "inspect":
            return 0
    records = pd.read_csv(output / "video_inventory.csv").to_dict("records")
    if args.video:
        records = [record for record in records if Path(record["source_path"]).resolve() == args.video.resolve()]
    elif args.samples:
        records = [record for record in records if record["video_id"] in args.samples]
        if len(records) != len(set(args.samples)):
            raise SystemExit("Requested sample ID is absent from inventory")
    elif (output / "selection.json").exists():
        selected = read_json(output / "selection.json")["selected_video_ids"]
        records = [record for record in records if record["video_id"] in selected]
    elif args.command != "report":
        raise SystemExit("Use --samples or persist selection.json; will not process all videos implicitly")
    if args.command in {"run-all", "sfm"} and len(records) > 3:
        raise SystemExit("Phase 01 guard: at most three real videos may receive full SfM")
    failures = []
    for record in records:
        directory = output / record["video_id"]
        commands = ["extract", "quality", "segment", "sfm", "analyze"] if args.command == "run-all" else [args.command]
        try:
            for command in commands:
                force = args.force or args.no_reuse or command in args.rerun_stage
                if command == "extract":
                    supplemental = read_json(args.supplemental_times) if args.supplemental_times else None
                    if isinstance(supplemental, dict):
                        supplemental = supplemental["timestamps"]
                    extract(record, configuration, force, supplemental)
                elif command == "quality":
                    from mdrd.quality import analyze_quality
                    analyze_quality(directory, configuration, force)
                elif command == "segment":
                    from mdrd.segmentation import coarse_segment
                    coarse_segment(directory, configuration, force, args.override)
                elif command == "sfm":
                    from mdrd.sfm import run_sfm
                    run_sfm(directory, configuration, force)
                elif command == "analyze":
                    from mdrd.geometry.analysis import analyze
                    analyze(directory, configuration, force)
        except Exception as exception:
            failures.append({"video_id": record["video_id"], "stage": command, "error": repr(exception), "traceback": traceback.format_exc()})
            print(traceback.format_exc(), flush=True)
    if failures:
        write_json(output / "last_failures.json", failures)
    if args.command in {"report", "run-all"}:
        from mdrd.reporting.reports import generate_reports
        generate_reports(configuration, [record["video_id"] for record in records])
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
