#!/usr/bin/env bash
# Verify feature lead-gdrive-assets trên VPS và thu bằng chứng để merge.
# Chạy trên VPS: cd /opt/aiplatform && chmod +x scripts/verify_vps_lead_gdrive.sh && ./scripts/verify_vps_lead_gdrive.sh
#
# Output lưu: /tmp/verify_ports_ufw.txt, /tmp/smoke_e2e_output.txt, /tmp/publish_trace.txt
# Sau khi chạy: paste các file vào RUNBOOK_SMOKE_TEST.md và RUNBOOK_SECURITY.md theo hướng dẫn in ra cuối script.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/aiplatform}"
cd "$REPO_ROOT"
API_CONTAINER="${API_CONTAINER:-ai-content-director-api}"

echo "=== Verify feature lead-gdrive-assets (VPS) ==="
echo "REPO_ROOT=$REPO_ROOT  API_CONTAINER=$API_CONTAINER"
echo ""

# --- 1) Security verify ---
echo "--- 1) Security verify ---"
docker compose ps
echo ""
echo "Ports (ss -lntp):"
ss -lntp 2>/dev/null | egrep ':(8000|5432|6379)\b' || true
echo ""
echo "UFW (nếu có):"
ufw status verbose 2>/dev/null || true
echo ""

# Lưu ports/ufw cho paste vào RUNBOOK_SECURITY.md
{
  echo "=== docker compose ps ==="
  docker compose ps
  echo ""
  echo "=== ss -lntp | egrep ':(8000|5432|6379)' ==="
  ss -lntp 2>/dev/null | egrep ':(8000|5432|6379)\b' || true
  echo ""
  echo "=== ufw status verbose ==="
  ufw status verbose 2>/dev/null || true
} | tee /tmp/verify_ports_ufw.txt
echo "  -> Đã lưu /tmp/verify_ports_ufw.txt"
echo ""

# --- 2) Run migrations ---
echo "--- 2) Run migrations ---"
docker exec "$API_CONTAINER" sh -c "cd /app && alembic upgrade head"
echo "  -> Migrations xong"
echo ""

# --- 3) Smoke E2E ---
echo "--- 3) Smoke E2E ---"
chmod +x scripts/smoke_e2e.sh
set +e
./scripts/smoke_e2e.sh 2>&1 | tee /tmp/smoke_e2e_output.txt
SMOKE_EXIT=${PIPESTATUS[0]}
set -e
echo "  -> Đã lưu /tmp/smoke_e2e_output.txt (exit=$SMOKE_EXIT)"
if [ "$SMOKE_EXIT" -ne 0 ]; then
  echo "  [WARN] Smoke E2E trả về exit $SMOKE_EXIT (xem /tmp/smoke_e2e_output.txt)."
fi
echo ""

# --- 4) Logging verification (publish trace) ---
echo "--- 4) Publish trace (scheduler + facebook_publish logs) ---"
docker logs --tail=800 "$API_CONTAINER" 2>&1 | grep -E "scheduler\.tick|scheduler\.publish_result|facebook_publish\.(calling|success|fail)" | tail -n 200 | tee /tmp/publish_trace.txt
echo "  -> Đã lưu /tmp/publish_trace.txt"
echo ""

# --- Kết luận ports ---
echo "--- Kết luận ports (policy) ---"
if ss -lntp 2>/dev/null | grep -q '127.0.0.1:5432'; then
  echo "  [OK] Postgres bind 127.0.0.1:5432"
else
  echo "  [WARN] Postgres không thấy bind 127.0.0.1:5432 (kiểm tra ss -lntp)"
fi
if ss -lntp 2>/dev/null | grep -q '127.0.0.1:6379'; then
  echo "  [OK] Redis bind 127.0.0.1:6379"
else
  echo "  [WARN] Redis không thấy bind 127.0.0.1:6379 (kiểm tra ss -lntp)"
fi
echo ""

echo "=== Verify xong ==="
echo ""
echo "Cập nhật docs:"
echo "  1. Paste /tmp/smoke_e2e_output.txt vào RUNBOOK_SMOKE_TEST.md (phần Output mẫu)."
echo "  2. Paste /tmp/verify_ports_ufw.txt và /tmp/publish_trace.txt (hoặc trích) vào RUNBOOK_SECURITY.md (phần Verify trên VPS) hoặc RUNBOOK_SMOKE_TEST.md (phần Verify)."
echo "  Ví dụ: cat /tmp/smoke_e2e_output.txt"
echo "         cat /tmp/verify_ports_ufw.txt"
echo "         cat /tmp/publish_trace.txt"
