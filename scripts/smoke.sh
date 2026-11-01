#!/usr/bin/env bash
# M1 冒烟脚本：实际逻辑在 scripts/smoke.py，避免 bash / PowerShell 各写一份。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
exec "$PY" "$ROOT/scripts/smoke.py" "$@"
