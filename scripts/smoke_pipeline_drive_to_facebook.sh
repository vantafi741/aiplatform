#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Smoke test cho endpoint:
# POST /api/pipelines/drive_to_facebook/run
#
# Usage:
#   TENANT_ID=<uuid> bash ./scripts/smoke_pipeline_drive_to_facebook.sh
# Optional:
#   API_BASE_URL=http://127.0.0.1:8000

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
TENANT_ID="${TENANT_ID:-}"

if [[ -z "${TENANT_ID}" ]]; then
  echo "[FAIL] Missing TENANT_ID env"
  echo "Example: TENANT_ID=<uuid> bash ./scripts/smoke_pipeline_drive_to_facebook.sh"
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "[FAIL] jq is required for this smoke script"
  exit 1
fi

echo "[INFO] API_BASE_URL=${API_BASE_URL}"
echo "[INFO] TENANT_ID=${TENANT_ID}"

resp_file="$(mktemp)"
cleanup() {
  rm -f "${resp_file}"
}
trap cleanup EXIT

status_code="$(curl -sS -o "${resp_file}" -w "%{http_code}" \
  -X POST "${API_BASE_URL}/api/pipelines/drive_to_facebook/run" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"${TENANT_ID}\"}")"

echo "[INFO] HTTP ${status_code}"
echo "[INFO] Response JSON:"
jq . "${resp_file}" || cat "${resp_file}"

if [[ "${status_code}" =~ ^2[0-9]{2}$ ]]; then
  echo "[OK] smoke_pipeline_drive_to_facebook passed"
  exit 0
fi

echo "[FAIL] smoke_pipeline_drive_to_facebook failed"
exit 1
