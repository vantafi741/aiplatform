#!/usr/bin/env bash
# Smoke test Foundation Stack: health, migrate OK, n8n up.
# Chay tu repo root: ./scripts/smoke.sh
# Can: API dang chay (docker compose up hoac run_mvp_local), Postgres + Redis (+ n8n) chay.

set -e
BASE_URL="${BASE_URL:-http://localhost:8000}"
N8N_URL="${N8N_URL:-http://localhost:5678}"
FAIL=0

echo "=== Smoke test (Foundation Stack) ==="
echo "API: $BASE_URL"
echo ""

# 1) Curl health (healthz)
echo "[1/3] GET $BASE_URL/api/healthz"
if curl -sf "$BASE_URL/api/healthz" | grep -q '"status"' ; then
  echo "  OK"
else
  echo "  FAIL"
  FAIL=1
fi

# 2) Ready (DB + Redis) - dam bao app da migrate va ket noi duoc
echo "[2/3] GET $BASE_URL/api/readyz"
if curl -sf "$BASE_URL/api/readyz" | grep -q '"status".*"ok"' ; then
  echo "  OK (DB + Redis)"
else
  echo "  FAIL (readyz khong OK - kiem tra migrate va REDIS_URL)"
  FAIL=1
fi

# 3) n8n up
echo "[3/3] n8n up $N8N_URL"
if curl -sf --max-time 5 "$N8N_URL/healthz" >/dev/null 2>&1 ; then
  echo "  OK"
elif curl -sf --max-time 5 "$N8N_URL/" >/dev/null 2>&1 ; then
  echo "  OK (n8n root)"
else
  echo "  SKIP (n8n khong chay hoac khong mo port)"
fi

echo ""
if [ $FAIL -eq 0 ]; then
  echo "PASS"
  exit 0
else
  echo "FAIL"
  exit 1
fi
