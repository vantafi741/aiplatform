#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Smoke test cho endpoint:
# POST /api/pipelines/drive_to_facebook/run
#
# Usage:
#   TENANT_ID=<uuid> bash /app/scripts/smoke_pipeline_drive_to_facebook.sh
# Optional:
#   API_BASE_URL=http://127.0.0.1:8000

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
TENANT_ID="${TENANT_ID:-}"

if [[ -z "${TENANT_ID}" ]]; then
  echo "[FAIL] Missing TENANT_ID env"
  echo "Example: TENANT_ID=<uuid> bash /app/scripts/smoke_pipeline_drive_to_facebook.sh"
  exit 1
fi

echo "[INFO] API_BASE_URL=${API_BASE_URL}"
echo "[INFO] TENANT_ID=${TENANT_ID}"

curl -sS -X POST "${API_BASE_URL}/api/pipelines/drive_to_facebook/run" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"${TENANT_ID}\"}"
echo
