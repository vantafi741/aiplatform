#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"
IFS=$'\n\t'

# Runtime audit (portable: local + VPS). No business logic changes.

REPO_ROOT="${REPO_ROOT:-$PROJECT_ROOT}"
API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
RAW_FILE="${RAW_FILE:-${REPO_ROOT}/docs/.runtime_audit_raw.txt}"
REPORT_FILE="${REPORT_FILE:-${REPO_ROOT}/docs/RUNTIME_AUDIT_REPORT.md}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-ai-ecosystem-postgres}"
API_CONTAINER="${API_CONTAINER:-ai-content-director-api}"
DB_NAME="${DB_NAME:-ai_content_director}"
DB_USER="${DB_USER:-postgres}"

MODE="VPS"
case "${PROJECT_ROOT}" in
  /mnt/*|*:/*)
    MODE="LOCAL"
    ;;
esac

write_section() {
  local key="$1"
  shift
  {
    echo "###BEGIN:${key}"
    "$@" 2>&1 || echo "[ERROR] command failed: $*"
    echo "###END:${key}"
  } >> "${RAW_FILE}"
}

write_section_shell() {
  local key="$1"
  local cmd="$2"
  {
    echo "###BEGIN:${key}"
    bash -lc "${cmd}" 2>&1 || echo "[ERROR] command failed: ${cmd}"
    echo "###END:${key}"
  } >> "${RAW_FILE}"
}

echo "# runtime_audit_raw" > "${RAW_FILE}"
echo "mode=${MODE}" >> "${RAW_FILE}"
echo "generated_at=$(date -Iseconds 2>/dev/null || date)" >> "${RAW_FILE}"
echo "repo_root=${REPO_ROOT}" >> "${RAW_FILE}"
echo "api_base_url=${API_BASE_URL}" >> "${RAW_FILE}"

# 1) git branch + last commit
write_section_shell "GIT" "echo branch=\$(git branch --show-current || true); echo last_commit=\$(git log -1 --oneline || true)"

# 2) docker compose ps (health)
write_section "DOCKER_PS" docker compose ps

# 3) api logs tail 200
write_section "API_LOGS" docker compose logs --tail 200 api

# 4) curl /api/healthz
write_section_shell "HEALTHZ" "code=\$(curl -sS -o /tmp/healthz.json -w '%{http_code}' '${API_BASE_URL}/api/healthz' || true); echo http_code=\${code}; [ -f /tmp/healthz.json ] && cat /tmp/healthz.json || true"

# 5) curl /openapi.json (count paths)
write_section_shell "OPENAPI" "code=\$(curl -sS -o /tmp/openapi.json -w '%{http_code}' '${API_BASE_URL}/openapi.json' || true); echo http_code=\${code}; if [ \"\${code}\" = \"200\" ]; then python3 -c \"import json; d=json.load(open('/tmp/openapi.json','r',encoding='utf-8')); print('paths_count='+str(len(d.get('paths', {}))))\"; else echo paths_count=n/a; fi"

# 6) psql: tables + row counts top 15
write_section "DB_TABLES" docker exec "${POSTGRES_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -c "\dt"
write_section_shell "DB_ROW_COUNTS" "for t in tenants brand_profiles industry_profile generated_plans content_plans content_items revenue_content_items content_assets asset_summaries publish_logs approval_events post_metrics ai_usage_logs lead_signals kb_items; do c=\$(docker exec '${POSTGRES_CONTAINER}' psql -U '${DB_USER}' -d '${DB_NAME}' -t -A -c \"SELECT count(*) FROM \${t};\" 2>/dev/null | tr -d '[:space:]' || true); if [ -z \"\${c}\" ]; then c='n/a'; fi; echo \"\${t}=\${c}\"; done"

# 7) alembic current + history (10)
write_section "ALEMBIC_CURRENT" docker exec "${API_CONTAINER}" sh -lc "cd /app && alembic current"
write_section "ALEMBIC_HISTORY" docker exec "${API_CONTAINER}" sh -lc "cd /app && alembic history | tail -n 10"

# 8) env check (length only, no secrets)
write_section_shell "ENV_LENGTHS" "docker exec '${API_CONTAINER}' sh -lc 'for k in APP_ENV DATABASE_URL REDIS_URL OPENAI_API_KEY OPENAI_MODEL OPENAI_VISION_MODEL FACEBOOK_PAGE_ID FACEBOOK_ACCESS_TOKEN FB_PAGE_ACCESS_TOKEN GDRIVE_SA_JSON_PATH GDRIVE_READY_IMAGES_FOLDER_ID GDRIVE_READY_VIDEOS_FOLDER_ID GDRIVE_PROCESSED_FOLDER_ID GDRIVE_REJECTED_FOLDER_ID WEBHOOK_URL API_BASE_URL TENANT_ID ENABLE_INTERNAL_SCHEDULER DISABLE_SCHEDULER; do v=\$(printenv \"\$k\" || true); if [ -n \"\$v\" ]; then echo \"\$k len=\${#v}\"; else echo \"\$k len=0\"; fi; done'"

python3 "${REPO_ROOT}/scripts/audit_fill_report.py" \
  --raw "${RAW_FILE}" \
  --out "${REPORT_FILE}" \
  --repo-root "${REPO_ROOT}" \
  --api-base-url "${API_BASE_URL}"

echo "Audit completed."
echo "Raw:    ${RAW_FILE}"
echo "Report: ${REPORT_FILE}"
