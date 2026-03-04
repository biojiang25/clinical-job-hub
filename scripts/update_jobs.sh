#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p data

echo "[update] running collector..."
set +e
python3 collector/fetch_daily_jobs.py "$@"
EXIT_CODE=$?
set -e

if [ ! -f data/jobs_latest.json ]; then
  echo '{"generated_at":"","total":0,"items":[]}' > data/jobs_latest.json
fi
if [ ! -f data/jobs_today.json ]; then
  echo '{"generated_at":"","total":0,"items":[]}' > data/jobs_today.json
fi
if [ ! -f data/fetch_report.json ]; then
  echo '{"started_at":"","finished_at":"","sources":0,"scanned":0,"accepted":0,"inserted":0,"updated":0,"errors":[],"dry_run":false}' > data/fetch_report.json
fi

python3 - <<'PY'
import json
from pathlib import Path

report = Path("data/fetch_report.json")
if not report.exists():
    print("[update] report missing")
else:
    data = json.loads(report.read_text(encoding="utf-8"))
    print("[update] finished_at:", data.get("finished_at"))
    print("[update] scanned:", data.get("scanned"), "accepted:", data.get("accepted"))
    print("[update] inserted:", data.get("inserted"), "updated:", data.get("updated"))
    print("[update] errors:", len(data.get("errors", [])))
PY

if [ "$EXIT_CODE" -ne 0 ]; then
  echo "[update] collector exited with code $EXIT_CODE (report generated)."
fi

exit 0
