#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Fast & safe deploy script (portable: Ubuntu VPS + WSL/Git Bash).
# Usage:
#   bash scripts/deploy_vps.sh <branch_or_tag>

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

if [ "${1:-}" = "" ]; then
  echo "Usage: bash scripts/deploy_vps.sh <branch_or_tag>"
  exit 1
fi

TARGET_REF="$1"
REPORT_PATH="$PROJECT_ROOT/docs/RUNTIME_AUDIT_REPORT.md"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/healthz}"
HEALTH_RETRIES="${HEALTH_RETRIES:-5}"

echo "[INFO] PROJECT_ROOT=$PROJECT_ROOT"
echo "[INFO] TARGET_REF=$TARGET_REF"

echo "[STEP] git fetch --all --prune"
git fetch --all --prune --tags

is_tag=0
if git rev-parse -q --verify "refs/tags/$TARGET_REF" >/dev/null; then
  is_tag=1
elif git ls-remote --tags origin "refs/tags/$TARGET_REF" | grep -q .; then
  is_tag=1
fi

if [ "$is_tag" -eq 1 ]; then
  echo "[STEP] checkout tag: $TARGET_REF"
  git checkout "tags/$TARGET_REF"
else
  echo "[STEP] checkout branch: $TARGET_REF"
  if ! git checkout "$TARGET_REF"; then
    git checkout -b "$TARGET_REF" "origin/$TARGET_REF"
  fi
  echo "[STEP] git pull origin $TARGET_REF"
  git pull origin "$TARGET_REF"
fi

echo "[STEP] docker compose down"
docker compose down

echo "[STEP] docker compose up -d --build"
docker compose up -d --build

echo "[STEP] docker compose ps"
docker compose ps

echo "[STEP] health check retry ($HEALTH_RETRIES times): $HEALTH_URL"
health_ok=0
for i in $(seq 1 "$HEALTH_RETRIES"); do
  code="$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" || true)"
  if [ "$code" = "200" ]; then
    echo "[OK] healthz is ready (attempt $i/$HEALTH_RETRIES)"
    health_ok=1
    break
  fi
  echo "[WAIT] healthz not ready (attempt $i/$HEALTH_RETRIES, code=$code)"
  sleep 3
done
if [ "$health_ok" -ne 1 ]; then
  echo "[FAIL] healthz failed after $HEALTH_RETRIES attempts"
  exit 1
fi

echo "[STEP] alembic upgrade head"
docker compose run --rm api alembic upgrade head

if [ -f "$PROJECT_ROOT/scripts/smoke_pipeline_run.sh" ]; then
  echo "[STEP] smoke pipeline run"
  if [ -n "${TENANT_ID:-}" ]; then
    TENANT_ID="${TENANT_ID}" bash "$PROJECT_ROOT/scripts/smoke_pipeline_run.sh"
  else
    echo "[WARN] TENANT_ID is empty -> skip smoke_pipeline_run.sh"
  fi
else
  echo "[INFO] scripts/smoke_pipeline_run.sh not found -> skip"
fi

if [ -f "$PROJECT_ROOT/scripts/audit_runtime_vps.sh" ]; then
  echo "[STEP] runtime audit report"
  bash "$PROJECT_ROOT/scripts/audit_runtime_vps.sh"
else
  echo "[WARN] scripts/audit_runtime_vps.sh not found -> skip"
fi

echo "[DONE] Deploy completed successfully."
echo "[DONE] Runtime report: $REPORT_PATH"
