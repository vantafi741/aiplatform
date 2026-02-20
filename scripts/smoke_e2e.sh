#!/usr/bin/env bash
# Smoke E2E: scheduler + publish pipeline.
# Flow: tenant -> onboarding industry -> plans/generate -> materialize -> content list ->
#       approve 1 item -> schedule (scheduled_at = now + 1 min) -> wait 90s ->
#       GET /publish/logs và /audit/events.
#
# Usage:
#   BASE_URL=http://127.0.0.1:8000 TENANT_NAME="Smoke E2E" INDUSTRY="Tech" ./scripts/smoke_e2e.sh
#   ./scripts/smoke_e2e.sh   # uses defaults: BASE_URL=http://127.0.0.1:8000, TENANT_NAME=SmokeE2E, INDUSTRY=Tech

set -e

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TENANT_NAME="${TENANT_NAME:-SmokeE2E}"
INDUSTRY="${INDUSTRY:-Tech}"

echo "=== Smoke E2E (scheduler + publish pipeline) ==="
echo "BASE_URL=$BASE_URL  TENANT_NAME=$TENANT_NAME  INDUSTRY=$INDUSTRY"
echo ""

# --- 1) Health ---
echo "[1/10] GET /health"
health=$(curl -s -S "$BASE_URL/health")
if ! echo "$health" | grep -q '"status"' || ! echo "$health" | grep -q 'ok'; then
  echo "FAIL: health not ok: $health"
  exit 1
fi
echo "  OK"

# --- 2) POST /api/tenants ---
echo "[2/10] POST /api/tenants"
tenant_resp=$(curl -s -S -X POST "$BASE_URL/api/tenants" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$TENANT_NAME\",\"industry\":\"$INDUSTRY\"}")
TENANT_ID=$(echo "$tenant_resp" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
if [ -z "$TENANT_ID" ]; then
  echo "FAIL: no tenant id in response: $tenant_resp"
  exit 1
fi
echo "  tenant_id=$TENANT_ID"

# --- 3) POST /api/onboarding (industry profile) ---
echo "[3/10] POST /api/onboarding"
onb_resp=$(curl -s -S -X POST "$BASE_URL/api/onboarding" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_ID\",\"name\":\"$INDUSTRY\",\"description\":\"Smoke test industry profile\"}")
if ! echo "$onb_resp" | grep -q '"tenant_id"'; then
  echo "WARN: onboarding response: $onb_resp"
fi
echo "  OK"

# --- 4) POST /api/plans/generate ---
echo "[4/10] POST /api/plans/generate"
plan_resp=$(curl -s -S -X POST "$BASE_URL/api/plans/generate" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_ID\"}")
if command -v jq &>/dev/null; then
  PLAN_ID=$(echo "$plan_resp" | jq -r '.plan.id // empty')
fi
if [ -z "$PLAN_ID" ]; then
  PLAN_ID=$(echo "$plan_resp" | grep -oE '"id"\s*:\s*"[a-f0-9-]+"' | head -1 | sed 's/.*"\([a-f0-9-]*\)"$/\1/')
fi
if [ -z "$PLAN_ID" ]; then
  echo "FAIL: no plan id in response: $plan_resp"
  exit 1
fi
echo "  plan_id=$PLAN_ID"

# --- 5) POST /api/plans/{plan_id}/materialize ---
echo "[5/10] POST /api/plans/$PLAN_ID/materialize"
mat_resp=$(curl -s -S -X POST "$BASE_URL/api/plans/$PLAN_ID/materialize" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_ID\"}")
echo "  $mat_resp"

# --- 6) GET /content/list?tenant_id=... ---
echo "[6/10] GET /content/list?tenant_id=$TENANT_ID"
list_resp=$(curl -s -S "$BASE_URL/content/list?tenant_id=$TENANT_ID")
if command -v jq &>/dev/null; then
  CONTENT_ID=$(echo "$list_resp" | jq -r '.items[0].id // empty')
else
  # Fallback: first UUID in "items" (second "id" in payload is first item id)
  CONTENT_ID=$(echo "$list_resp" | grep -oE '"id"\s*:\s*"[a-f0-9-]+"' | sed 's/.*"\([a-f0-9-]*\)"$/\1/' | sed -n '2p')
fi
if [ -z "$CONTENT_ID" ]; then
  echo "FAIL: no content item in list: $list_resp"
  exit 1
fi
echo "  content_id=$CONTENT_ID"

# --- 7) POST /content/{content_id}/approve ---
echo "[7/10] POST /content/$CONTENT_ID/approve"
approve_resp=$(curl -s -S -X POST "$BASE_URL/content/$CONTENT_ID/approve" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_ID\",\"actor\":\"HUMAN\"}")
if ! echo "$approve_resp" | grep -q 'approved'; then
  echo "WARN: approve response: $approve_resp"
fi
echo "  OK"

# --- 8) POST /content/{content_id}/schedule (scheduled_at = now + 1 minute) ---
# ISO 8601 UTC (GNU date: -d "+1 minute"; macOS: -v+1M)
NOW_PLUS_1MIN=$(python3 -c "from datetime import datetime, timezone, timedelta; print((datetime.now(timezone.utc) + timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ'))" 2>/dev/null) || \
  NOW_PLUS_1MIN=$(date -u -d "+1 minute" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null) || \
  NOW_PLUS_1MIN=$(date -u -v+1M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)
echo "[8/10] POST /content/$CONTENT_ID/schedule (scheduled_at=$NOW_PLUS_1MIN)"
schedule_resp=$(curl -s -S -X POST "$BASE_URL/content/$CONTENT_ID/schedule" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_ID\",\"scheduled_at\":\"$NOW_PLUS_1MIN\"}")
echo "  $schedule_resp"

# --- 9) Wait 90s for scheduler to pick up and (attempt) publish ---
echo "[9/10] Waiting 90s for scheduler tick..."
sleep 90

# --- 10) GET /publish/logs and /audit/events ---
echo "[10/10] GET /publish/logs and /audit/events"
echo "--- /publish/logs?tenant_id=$TENANT_ID&limit=10 ---"
curl -s -S "$BASE_URL/publish/logs?tenant_id=$TENANT_ID&limit=10" | head -100
echo ""
echo "--- /audit/events?tenant_id=$TENANT_ID&limit=20 ---"
curl -s -S "$BASE_URL/audit/events?tenant_id=$TENANT_ID&limit=20" | head -100

echo ""
echo "=== Smoke E2E done ==="
