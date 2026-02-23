#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Smoke test scheduler publish tick:
# 1) Chọn 1 draft item của tenant và chuyển thành approved/scheduled/due-now
# 2) Call POST /api/scheduler/run_publish_tick
# 3) Check lại schedule_status trong DB
#
# Usage:
#   TENANT_ID=<uuid> bash ./scripts/smoke_scheduler_publish.sh
#
# Optional:
#   API_BASE_URL=http://127.0.0.1:8000
#   PG_CONTAINER=ai-ecosystem-postgres
#   PG_DB=ai_content_director
#   PG_USER=postgres

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
TENANT_ID="${TENANT_ID:-}"
PG_CONTAINER="${PG_CONTAINER:-ai-ecosystem-postgres}"
PG_DB="${PG_DB:-ai_content_director}"
PG_USER="${PG_USER:-postgres}"

if [[ -z "${TENANT_ID}" ]]; then
  echo "[FAIL] Missing TENANT_ID env"
  exit 1
fi

echo "[INFO] TENANT_ID=${TENANT_ID}"
echo "[INFO] API_BASE_URL=${API_BASE_URL}"
echo "[INFO] PG_CONTAINER=${PG_CONTAINER}"

CONTENT_ID="$(docker exec "${PG_CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -t -A -c \
"SELECT id
 FROM content_items
 WHERE tenant_id = '${TENANT_ID}'
   AND status = 'draft'
 ORDER BY created_at DESC
 LIMIT 1;")"

if [[ -z "${CONTENT_ID}" ]]; then
  echo "[FAIL] No draft content_items for tenant=${TENANT_ID}"
  exit 1
fi

echo "[INFO] Picked content_id=${CONTENT_ID}"

docker exec "${PG_CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -c \
"UPDATE content_items
 SET status='approved',
     schedule_status='scheduled',
     require_media=false,
     scheduled_at=NOW() - INTERVAL '1 minute',
     last_publish_error=NULL
 WHERE id='${CONTENT_ID}';" >/dev/null

echo "[INFO] Trigger run_publish_tick..."
curl -sS -X POST "${API_BASE_URL}/scheduler/run_publish_tick" \
  -H "Content-Type: application/json" \
  -d '{"batch_size":5}'
echo

FINAL_STATUS="$(docker exec "${PG_CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -t -A -c \
"SELECT coalesce(schedule_status, 'NULL')
 FROM content_items
 WHERE id='${CONTENT_ID}';")"

echo "[INFO] Final schedule_status=${FINAL_STATUS}"
if [[ "${FINAL_STATUS}" == "published" ]]; then
  echo "[OK] Scheduler publish tick smoke passed"
else
  echo "[WARN] Not published yet. Current status=${FINAL_STATUS}"
fi
