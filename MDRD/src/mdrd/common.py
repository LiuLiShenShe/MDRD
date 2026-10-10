from __future__ import annotations

import copy
import csv
import hashlib
import importlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml


def now():
    return datetime.now(timezone.utc).isoformat()


def serializable(value):
    if isinstance(value, dict):
        return {str(key): serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(item) for item in value]
    if isinstance(value, (np.ndarray,)):
        return serializable(value.tolist())
    if isinstance(value, np.generic):
        return serializable(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(serializable(value), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_image_inputs(manifest_path):
    manifest_path = Path(manifest_path)
    if not manifest_path.is_file():
        return []
    with manifest_path.open(newline="", encoding="utf-8") as stream:
        rows = csv.DictReader(stream)
        paths = []
        for row in rows:
            value = row.get("image_path")
            if not value:
                continue
            path = Path(value)
            paths.append(path if path.is_absolute() else manifest_path.parent / path)
    return paths


def merge(target, source):
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge(target[key], value)
        else:
            target[key] = value
    return target


def load_config(path=None, overrides=None):
    default = Path(__file__).resolve().parents[2] / "configs" / "default.yaml"
    configuration = yaml.safe_load(default.read_text())
    if path:
        merge(configuration, yaml.safe_load(Path(path).read_text()) or {})
    merge(configuration, overrides or {})
    configuration["project_root"] = str(Path(configuration["project_root"]).resolve()) if overrides and "project_root" in overrides else str(default.parents[2])
    root = Path(configuration["project_root"])
    output = Path(configuration["output_root"])
    configuration["output_root"] = str(output if output.is_absolute() else root / output)
    return configuration


def run_command(command, log_path, allow_failure=False, timeout=None):
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    archived_log = None
    if log_path.exists():
        archive_directory = log_path.parent / "history"
        archive_directory.mkdir(exist_ok=True)
        archived_log = archive_directory / f"{log_path.stem}_{uuid.uuid4().hex[:12]}{log_path.suffix}"
        log_path.rename(archived_log)
    started = time.perf_counter()
    environment = os.environ.copy()
    environment.setdefault("QT_QPA_PLATFORM", "offscreen")
    with log_path.open("w", encoding="utf-8") as stream:
        stream.write("COMMAND " + json.dumps([str(item) for item in command], ensure_ascii=False) + "\n")
        stream.flush()
        try:
            result = subprocess.run([str(item) for item in command], stdout=stream, stderr=subprocess.STDOUT, env=environment, timeout=timeout)
            returncode = result.returncode
        except subprocess.TimeoutExpired:
            returncode = -124
    record = {"timestamp": now(), "command": [str(item) for item in command], "returncode": returncode, "elapsed_sec": time.perf_counter() - started, "log": str(log_path), "log_sha256": sha256(log_path), "archived_previous_log": str(archived_log) if archived_log else None}
    with (log_path.parent / "commands.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    if returncode and not allow_failure:
        raise RuntimeError(f"Command returned {returncode}: see {log_path}")
    return record


def capture(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        return {"returncode": result.returncode, "text": (result.stdout + result.stderr).strip()}
    except Exception as exception:
        return {"returncode": None, "error": str(exception)}


def environment_report(output, executable="colmap"):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    packages = {}
    for name in ["cv2", "numpy", "pandas", "scipy", "matplotlib", "plotly", "pycolmap", "yaml", "pytest"]:
        try:
            module = importlib.import_module(name)
            packages[name] = {"version": getattr(module, "__version__", None), "path": getattr(module, "__file__", None)}
        except Exception as exception:
            packages[name] = {"error": str(exception)}
    tools = {name: capture([name, "-version"]) for name in ["ffmpeg", "ffprobe"]}
    tools["colmap"] = capture([executable, "-h"])
    for command in ["feature_extractor", "matches_importer", "exhaustive_matcher", "mapper", "image_registrator", "point_triangulator", "bundle_adjuster"]:
        result = capture([executable, command, "-h"])
        (output / "logs").mkdir(exist_ok=True)
        (output / "logs" / f"colmap_{command}_help.txt").write_text(result.get("text", result.get("error", "")))
    disk = shutil.disk_usage(output)
    report = {"created_at": now(), "os": platform.platform(), "python": sys.version, "python_executable": sys.executable, "packages": packages, "tools": tools, "gpu": capture(["nvidia-smi"]), "cuda": capture(["nvcc", "--version"]), "disk_bytes": {"total": disk.total, "used": disk.used, "free": disk.free}, "pycolmap_has_cuda": bool(getattr(importlib.import_module("pycolmap"), "has_cuda", False))}
    write_json(output / "environment_report.json", report)
    return report


@contextmanager
def stage(directory, name, parameters, inputs=(), force=False, required_outputs=()):
    directory = Path(directory)
    progress = directory / "progress"
    progress.mkdir(parents=True, exist_ok=True)
    module_directories = {"extract": ["video"], "quality": ["quality", "visualization"], "segment": ["segmentation", "visualization"], "sfm": ["sfm"], "analyze": ["geometry", "segmentation", "visualization", "sfm"], "foreground": ["geometry"], "report": ["reporting"]}
    source_root = Path(__file__).parent
    sources = [source_root / "common.py"]
    if name == "foreground":
        sources.append(source_root / "phase1b" / "foreground.py")
    for module_name in module_directories.get(name, []):
        sources.extend((source_root / module_name).rglob("*.py"))
    input_signatures = {}
    for input_path in inputs:
        path = Path(input_path)
        if path.is_file():
            input_signatures[str(path)] = sha256(path)
        elif path.is_dir():
            input_signatures[str(path)] = {str(item.relative_to(path)): sha256(item) for item in sorted(path.rglob("*")) if item.is_file()}
        else:
            input_signatures[str(path)] = "MISSING"
    signature_data = {"parameters": parameters, "inputs": input_signatures, "code": {str(path.relative_to(source_root)): sha256(path) for path in sorted(sources)}}
    signature = hashlib.sha256(json.dumps(serializable(signature_data), sort_keys=True).encode()).hexdigest()
    status_path = progress / f"{name}.json"
    existing = read_json(status_path) if status_path.exists() else {}
    paths = required_outputs() if callable(required_outputs) else required_outputs
    current_outputs = {str(Path(path)): sha256(path) if Path(path).is_file() else None for path in paths}
    recorded_outputs = existing.get("output_hashes", {})
    outputs_valid = all(current_outputs.get(path) is not None and recorded_outputs.get(path) == current_outputs[path] for path in current_outputs)
    if not current_outputs:
        outputs_valid = True
    if not force and existing.get("signature") == signature and existing.get("status") == "completed" and outputs_valid:
        yield False
        return
    started = time.perf_counter()
    record = {"stage": name, "started_at": now(), "signature": signature, "configuration": copy.deepcopy(parameters), "status": "running"}
    write_json(status_path, record)
    try:
        yield True
    except Exception as exception:
        record.update(status="failed", error=f"{type(exception).__name__}: {exception}")
        raise
    else:
        record["status"] = "completed"
        paths = required_outputs() if callable(required_outputs) else required_outputs
        record["output_hashes"] = {str(Path(path)): sha256(path) if Path(path).is_file() else None for path in paths}
    finally:
        record.update(finished_at=now(), elapsed_sec=time.perf_counter() - started)
        write_json(status_path, record)
        with (progress / "history.jsonl").open("a") as stream:
            stream.write(json.dumps(serializable(record), ensure_ascii=False) + "\n")
