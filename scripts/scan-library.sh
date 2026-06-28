#!/usr/bin/env bash
# Run a library scan from cron (activates venv, logs to data/scan.log).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/data/scan.log"

{
  echo "=== $(date -Is) scan start ==="
  if [[ -f "$ROOT/.venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$ROOT/.venv/bin/activate"
  fi
  sonus scan
  echo "=== $(date -Is) scan done ==="
} >>"$LOG" 2>&1
