#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Smoke test cho single-source orchestrator pipeline.
# Usage:
#   TENANT_ID=<uuid> bash scripts/smoke_pipeline_run.sh

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TENANT_ID="${TENANT_ID:-}"

if [ -z "${TENANT_ID}" ]; then
  echo "TENANT_ID is required"
  echo "Example: TENANT_ID=<uuid> bash scripts/smoke_pipeline_run.sh"
  exit 1
fi

echo "[1/3] Run pipeline endpoint"
curl -sS -X POST "${BASE_URL}/api/pipelines/drive_to_facebook/run" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"${TENANT_ID}\",\"options\":{\"mode\":\"full\",\"limit\":3}}" | tee /tmp/pipeline_run.json

echo
echo "[2/3] Validate response keys"
python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/pipeline_run.json").read_text(encoding="utf-8"))
required = [
    "ingested",
    "summarized",
    "generated",
    "approved",
    "published",
    "metrics_fetched",
    "errors",
]
missing = [k for k in required if k not in payload]
if missing:
    raise SystemExit(f"Missing keys: {missing}")
print("Response shape OK")
PY

echo "[3/3] Suggested log verification order"
echo "docker compose logs --tail=200 api | grep -E \"orchestrator.step.ingest_done|orchestrator.step.assets_selected|orchestrator.pipeline.done\""
