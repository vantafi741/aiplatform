#!/usr/bin/env bash
# Smoke test: HITL Approval + Scheduler auto-publish
# Luồng: generate plan → materialize → set scheduled_at = now-1min → approve → đợi 90s → kiểm tra published + publish_logs
# Cần: server chạy, SCHEDULER_ENABLED=true, SCHEDULER_TENANT_ID trùng tenant (hoặc bỏ để quét mọi tenant)
# Usage: ./scripts/smoke_test_approval_scheduler.sh [BASE_URL] [TENANT_ID]

set -e
BASE_URL="${1:-http://localhost:8000}"
TENANT_ID="${2:?Pass TENANT_ID (UUID) as second argument}"

echo "=== 1) Generate plan ==="
RESP=$(curl -s -X POST "$BASE_URL/api/plans/generate?force=false&ai=true" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_ID\",\"days\":30}")
echo "$RESP" | head -c 500
echo ""
PLAN_ID=$(echo "$RESP" | grep -o '"plan_id":"[^"]*"' | cut -d'"' -f4)
if [ -z "$PLAN_ID" ]; then
  echo "FAIL: no plan_id in response"
  exit 1
fi
echo "plan_id=$PLAN_ID"

echo "=== 2) Materialize (channel=facebook) ==="
curl -s -X POST "$BASE_URL/api/plans/$PLAN_ID/materialize" \
  -H "Content-Type: application/json" \
  -d "{
    \"tenant_id\":\"$TENANT_ID\",
    \"timezone\":\"Asia/Ho_Chi_Minh\",
    \"posting_hours\":[\"09:00\",\"19:30\"],
    \"start_date\":\"2026-03-01\",
    \"channel\":\"facebook\",
    \"default_status\":\"draft\"
  }" | head -c 600
echo ""

echo "=== 3) Lấy item_id đầu tiên (draft) ==="
LIST=$(curl -s "$BASE_URL/api/content_items?tenant_id=$TENANT_ID&status=draft&limit=1")
ITEM_ID=$(echo "$LIST" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
if [ -z "$ITEM_ID" ]; then
  echo "FAIL: no draft item found"
  exit 1
fi
echo "item_id=$ITEM_ID"

echo "=== 4) Set scheduled_at = now - 1 phút (PATCH) ==="
# ISO timestamp UTC, 1 phút trước (portable: dùng Python)
SCHEDULED_AT=$(python3 -c "from datetime import datetime, timezone, timedelta; print((datetime.now(timezone.utc)-timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ'))")
curl -s -X PATCH "$BASE_URL/api/content_items/$ITEM_ID" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_ID\",\"scheduled_at\":\"$SCHEDULED_AT\"}"
echo ""

echo "=== 5) Approve item ==="
curl -s -X POST "$BASE_URL/api/content_items/$ITEM_ID/approve" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT_ID\",\"approved_by\":\"manual:smoke-test\"}"
echo ""

echo "=== 6) Đợi 90s cho scheduler đăng ==="
sleep 90

echo "=== 7) Kiểm tra GET /api/content_items?status=published có item ==="
PUBLISHED=$(curl -s "$BASE_URL/api/content_items?tenant_id=$TENANT_ID&status=published&limit=50")
if echo "$PUBLISHED" | grep -q "$ITEM_ID"; then
  echo "OK: item xuất hiện trong list published"
else
  echo "FAIL: item không có trong list published"
  echo "$PUBLISHED" | head -c 800
  exit 1
fi

echo "=== 8) Kiểm tra publish_logs có bản ghi cho content_id ==="
LOGS=$(curl -s "$BASE_URL/publish/logs?tenant_id=$TENANT_ID&limit=10")
if echo "$LOGS" | grep -q "$ITEM_ID"; then
  echo "OK: publish_logs có bản ghi cho content_id=$ITEM_ID"
else
  echo "FAIL: publish_logs không có bản ghi cho content_id=$ITEM_ID"
  echo "$LOGS" | head -c 600
  exit 1
fi

echo "=== Done (smoke test approval + scheduler passed) ==="
