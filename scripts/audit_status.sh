#!/usr/bin/env bash
# Enterprise audit trạng thái VPS – tạo REPORT_STATUS_VPS.md, không lộ secret.
# Chạy trên VPS: cd /opt/aiplatform && ./scripts/audit_status.sh
# Mask: 4 ký tự đầu + 4 ký tự cuối cho mọi token/URL.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/aiplatform}"
REPORT_FILE="${REPORT_FILE:-$REPO_ROOT/REPORT_STATUS_VPS.md}"
API_CONTAINER="${API_CONTAINER:-ai-content-director-api}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-ai-ecosystem-postgres}"
N8N_CONTAINER="${N8N_CONTAINER:-ai-ecosystem-n8n}"
LOG_LINES="${LOG_LINES:-200}"
BASE_URL="${BASE_URL:-http://localhost:8000}"

cd "$REPO_ROOT"
echo "Audit status -> $REPORT_FILE (REPO_ROOT=$REPO_ROOT)"

report() { echo "$1" >> "$REPORT_FILE"; }
report_section() {
  echo "" >> "$REPORT_FILE"
  echo "---" >> "$REPORT_FILE"
  echo "## $1" >> "$REPORT_FILE"
  echo "" >> "$REPORT_FILE"
}

# --- Header
echo "# BÁO CÁO TRẠNG THÁI VPS – AI PLATFORM" > "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "**Ngày tạo:** $(date -Iseconds 2>/dev/null || date)" >> "$REPORT_FILE"
echo "**Repo:** $REPO_ROOT" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# --- 1) Git
report_section "1) Git"
report '```'
report "Branch: $(git branch --show-current 2>/dev/null || echo 'n/a')"
report "Last commit: $(git log -1 --oneline 2>/dev/null || echo 'n/a')"
report ""
report "git status:"
git status --short 2>/dev/null >> "$REPORT_FILE" || report "n/a"
report '```'

# --- 2) Docker
report_section "2) Docker"
report "### docker compose ps"
report '```'
docker compose ps 2>/dev/null >> "$REPORT_FILE" || report "docker compose not available"
report '```'
report ""
report "### Images (relevant)"
report '```'
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" 2>/dev/null | head -20 >> "$REPORT_FILE" || true
report '```'
report ""
report "### Health & Ports"
report '```'
docker compose ps -a --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null >> "$REPORT_FILE" || true
report '```'

# --- 3) Logs
report_section "3) Logs (last $LOG_LINES lines)"
report "### API container ($API_CONTAINER)"
report '```'
docker compose logs --tail="$LOG_LINES" api 2>/dev/null >> "$REPORT_FILE" || docker logs --tail="$LOG_LINES" "$API_CONTAINER" 2>/dev/null >> "$REPORT_FILE" || report "No api logs"
report '```'
report ""
if docker compose config --services 2>/dev/null | grep -q worker; then
  report "### Worker container"
  report '```'
  docker compose logs --tail="$LOG_LINES" worker 2>/dev/null >> "$REPORT_FILE" || report "No worker logs"
  report '```'
fi

# --- 4) Endpoints
report_section "4) Endpoints"
report "Base URL: $BASE_URL"
report ""
report "| Endpoint | HTTP | Note |"
report "|----------|------|------|"
HZ=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/healthz" 2>/dev/null || echo "n/a")
report "| /api/healthz | $HZ | liveness |"
RZ=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/readyz" 2>/dev/null || echo "n/a")
report "| /api/readyz | $RZ | readiness (DB+Redis) |"
OAPI=$(curl -s -o /dev/null -w "%{http_code}" -X HEAD "$BASE_URL/openapi.json" 2>/dev/null || echo "n/a")
report "| /openapi.json (HEAD) | $OAPI | OpenAPI spec |"
report ""

# --- 5) ENV (masked: 4 head + 4 tail only)
report_section "5) ENV (keys quan trọng, giá trị mask 4 đầu + 4 cuối)"
report '```'
ENV_FILE=""
for f in "$REPO_ROOT/ai_content_director/.env" "$REPO_ROOT/.env"; do
  [ -f "$f" ] && { ENV_FILE="$f"; break; }
done
if [ -n "$ENV_FILE" ]; then
  python3 "$REPO_ROOT/scripts/audit_status.py" mask_env "$ENV_FILE" 2>/dev/null >> "$REPORT_FILE" || true
else
  report "# No .env found at ai_content_director/.env or .env"
fi
report '```'

# --- 6) DB
report_section "6) DB (PostgreSQL)"
report "### Tables (list)"
report '```'
docker exec "$POSTGRES_CONTAINER" psql -U postgres -d ai_content_director -c "\dt" 2>/dev/null >> "$REPORT_FILE" || report "Could not list tables (container or psql failed)"
report '```'
report ""
report "### Mô tả bảng chính"
report '```'
python3 "$REPO_ROOT/scripts/audit_status.py" table_descriptions 2>/dev/null >> "$REPORT_FILE" || true
report '```'
report ""
report "### Row counts (một số bảng)"
report '```'
for t in tenants content_items content_plans publish_logs lead_signals content_assets; do
  c=$(docker exec "$POSTGRES_CONTAINER" psql -U postgres -d ai_content_director -t -c "SELECT count(*) FROM $t" 2>/dev/null | tr -d ' \n' || echo "n/a")
  report "$t: $c"
done
report '```'

# --- 7) N8N (env masked: 4 head + 4 tail)
report_section "7) N8N"
report "Container status:"
report '```'
docker compose ps n8n 2>/dev/null >> "$REPORT_FILE" || docker ps -a --filter "name=$N8N_CONTAINER" 2>/dev/null >> "$REPORT_FILE" || true
report '```'
report ""
report "Webhook / N8N env (mask 4 đầu + 4 cuối):"
report '```'
docker exec "$N8N_CONTAINER" env 2>/dev/null | grep -E "WEBHOOK_URL|N8N_HOST|N8N_PROTOCOL" | python3 "$REPO_ROOT/scripts/audit_status.py" mask_env 2>/dev/null >> "$REPORT_FILE" || true
report '```'

# --- 8) Storage
report_section "8) Storage"
report "- Mount /data: $([ -d /data ] && echo 'exists' || echo 'not present')"
report "- LOCAL_MEDIA_DIR: xem mục 5 (masked)"
if [ -n "${ENV_FILE:-}" ] && [ -f "$ENV_FILE" ]; then
  MEDIA_DIR=$(grep -E "^LOCAL_MEDIA_DIR=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
  if [ -n "$MEDIA_DIR" ]; then
    report "  -> Path exists: $([ -d "$MEDIA_DIR" ] && echo 'yes' || echo 'no')"
  fi
fi

# --- 9) Disk / Memory
report_section "9) Disk & Memory snapshot"
report "### df -h"
report '```'
df -h 2>/dev/null >> "$REPORT_FILE" || report "n/a"
report '```'
report ""
report "### free -m"
report '```'
free -m 2>/dev/null >> "$REPORT_FILE" || report "n/a"
report '```'

echo "Done. Report: $REPORT_FILE"
