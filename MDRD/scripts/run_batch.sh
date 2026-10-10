#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$PROJECT_ROOT"
exec "$PROJECT_ROOT/.venv/bin/mdrd" run-all --samples video_007 video_008 video_020 "$@"
