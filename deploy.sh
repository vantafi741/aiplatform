#!/usr/bin/env bash
set -euo pipefail

# ==============================================================
# One-command deploy cho VPS: /opt/aiplatform
# Chay: ./deploy.sh
# ==============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

readonly COLOR_RED="\033[0;31m"
readonly COLOR_GREEN="\033[0;32m"
readonly COLOR_YELLOW="\033[1;33m"
readonly COLOR_BLUE="\033[0;34m"
readonly COLOR_RESET="\033[0m"

log_info() {
  echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} $*"
}

log_warn() {
  echo -e "${COLOR_YELLOW}[WARN]${COLOR_RESET} $*"
}

log_ok() {
  echo -e "${COLOR_GREEN}[OK]${COLOR_RESET} $*"
}

log_fail() {
  echo -e "${COLOR_RED}[FAIL]${COLOR_RESET} $*"
}

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    log_fail "Thieu lenh bat buoc: ${cmd}"
    exit 1
  fi
}

# Chon compose files theo thuc te. Co file prod thi uu tien include.
build_compose_cmd() {
  COMPOSE_ARGS=("-f" "docker-compose.yml")
  if [[ -f "docker-compose.prod.yml" ]]; then
    COMPOSE_ARGS+=("-f" "docker-compose.prod.yml")
    log_info "Su dung compose files: docker-compose.yml + docker-compose.prod.yml"
  else
    log_warn "Khong tim thay docker-compose.prod.yml, chi dung docker-compose.yml"
  fi
}

compose() {
  docker compose "${COMPOSE_ARGS[@]}" "$@"
}

wait_for_healthz() {
  local base_url="${1:-http://localhost:8000}"
  local timeout_secs="${2:-60}"
  local elapsed=0

  log_info "Cho API san sang: ${base_url}/api/healthz (timeout ${timeout_secs}s)"
  while (( elapsed < timeout_secs )); do
    if curl -fsS "${base_url}/api/healthz" >/dev/null 2>&1; then
      log_ok "API da healthy sau ${elapsed}s"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done

  log_fail "API khong healthy trong ${timeout_secs}s"
  return 1
}

main() {
  require_cmd git
  require_cmd docker
  require_cmd curl

  build_compose_cmd

  log_info "Kiem tra git status..."
  if [[ -n "$(git status --porcelain)" ]]; then
    log_fail "Repo dang co file chua commit. Deploy bi dung de an toan."
    echo "Huong dan:"
    echo "  1) Commit/stash thay doi local"
    echo "  2) Chay lai: ./deploy.sh"
    exit 1
  fi

  log_info "Cap nhat code moi nhat tu remote..."
  git fetch --all --prune
  current_branch="$(git rev-parse --abbrev-ref HEAD)"
  git pull --ff-only origin "${current_branch}"
  log_ok "Code da duoc cap nhat (fast-forward)."

  log_info "Build image..."
  compose build
  log_ok "Build thanh cong."

  log_info "Start/Update containers..."
  compose up -d --remove-orphans
  log_ok "Containers da duoc cap nhat."

  api_base_url="${API_BASE_URL:-http://localhost:8000}"
  wait_for_healthz "${api_base_url}" "${DEPLOY_HEALTH_TIMEOUT_SECONDS:-60}"

  log_info "Chay smoke test..."
  bash "./scripts/smoke_test.sh"
  log_ok "Smoke test passed."

  echo -e "${COLOR_GREEN}✅ DEPLOY SUCCESS${COLOR_RESET}"
}

if ! main "$@"; then
  echo -e "${COLOR_RED}❌ DEPLOY FAILED${COLOR_RESET}"
  exit 1
fi
