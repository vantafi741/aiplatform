#!/usr/bin/env bash
# Smoke test: Planner 30 ngày + Materialize
# Chạy khi server đã start (uvicorn). Cần TENANT_ID có sẵn (từ POST /onboarding).
# Usage: ./scripts/smoke_test_plans_materialize.sh [BASE_URL] [TENANT_ID]

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

echo "=== 2) Materialize ==="
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

echo "=== 3) Get plan ==="
curl -s "$BASE_URL/api/plans/$PLAN_ID" | head -c 800
echo ""

echo "=== Done ==="
