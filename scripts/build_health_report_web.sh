#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="$ROOT/.venv/bin/python"
PIP="$ROOT/.venv/bin/pip"

if [ ! -x "$PY" ]; then
  echo "missing virtualenv python: $PY" >&2
  exit 1
fi

$PY -m pip install -U pip pyinstaller

$PY -m PyInstaller --noconfirm --clean packaging/pyinstaller/health_report_web.spec

echo "build done: $ROOT/dist/HealthReportWeb"
