#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

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

COMPOSE_ARGS=()
COMPOSE_FILES=()
BUILD_LAST_LOG=""

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

show_failure_hints() {
  echo
  log_warn "Troubleshoot nhanh (copy/paste):"
  echo "$(compose_cmd_preview) ps"
  echo "$(compose_cmd_preview) logs --tail=200 api"
}

on_error() {
  log_fail "Deploy that bai tai line ${1}."
  show_failure_hints
}

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    log_fail "Thieu lenh bat buoc: ${cmd}"
    exit 1
  fi
}

detect_compose_file() {
  local base_file=""
  if [[ -f "docker-compose.yml" ]]; then
    base_file="docker-compose.yml"
  elif [[ -f "docker-compose.yaml" ]]; then
    base_file="docker-compose.yaml"
  elif [[ -f "compose.yml" ]]; then
    base_file="compose.yml"
  else
    log_fail "Khong tim thay file compose base (docker-compose.yml/.yaml hoac compose.yml)."
    exit 1
  fi

  COMPOSE_ARGS=("-f" "${base_file}")
  COMPOSE_FILES=("${base_file}")

  if [[ -f "docker-compose.prod.yml" ]]; then
    COMPOSE_ARGS+=("-f" "docker-compose.prod.yml")
    COMPOSE_FILES+=("docker-compose.prod.yml")
  elif [[ -f "docker-compose.prod.yaml" ]]; then
    COMPOSE_ARGS+=("-f" "docker-compose.prod.yaml")
    COMPOSE_FILES+=("docker-compose.prod.yaml")
  fi

  log_info "Compose files dang dung:"
  printf '  - %s\n' "${COMPOSE_FILES[@]}"
}

compose() {
  docker compose "${COMPOSE_ARGS[@]}" "$@"
}

compose_cmd_preview() {
  local cmd=("docker" "compose")
  cmd+=("${COMPOSE_ARGS[@]}")
  local out=""
  local part=""
  for part in "${cmd[@]}"; do
    out+=$(printf '%q ' "${part}")
  done
  printf '%s' "${out% }"
}

run_compose_build_capture() {
  local build_log
  build_log="$(mktemp)"
  if compose build 2>&1 | tee "${build_log}"; then
    BUILD_LAST_LOG=""
    rm -f "${build_log}"
    return 0
  fi

  BUILD_LAST_LOG="$(<"${build_log}")"
  rm -f "${build_log}"
  return 1
}

is_tls_timeout_error() {
  [[ "${BUILD_LAST_LOG}" == *"TLS handshake timeout"* ]] || [[ "${BUILD_LAST_LOG}" == *"net/http: TLS handshake timeout"* ]]
}

build_with_retry() {
  local -a backoffs=(3 10 20)
  local attempt=1
  local max_attempts=3

  while (( attempt <= max_attempts )); do
    log_info "Build attempt ${attempt}/${max_attempts}..."
    if run_compose_build_capture; then
      log_ok "Build thanh cong."
      return 0
    fi

    if ! is_tls_timeout_error; then
      log_fail "Build fail (khong phai loi TLS timeout) -> dung deploy."
      return 1
    fi

    if (( attempt == max_attempts )); then
      break
    fi

    local wait_seconds="${backoffs[$((attempt - 1))]}"
    log_warn "Gap loi mang TLS handshake timeout. Thu lai sau ${wait_seconds}s..."
    sleep "${wait_seconds}"
    attempt=$((attempt + 1))
  done

  log_fail "Build that bai sau ${max_attempts} lan (TLS handshake timeout)."
  log_warn "Neu chi can restart bang image hien tai, chay:"
  echo "DEPLOY_NO_BUILD=1 ./deploy.sh"
  return 1
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
  trap 'on_error ${LINENO}' ERR

  require_cmd git
  require_cmd docker
  require_cmd curl

  detect_compose_file

  log_info "Kiem tra git status..."
  if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
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

  if [[ "${DEPLOY_NO_BUILD:-0}" == "1" ]]; then
    log_warn "DEPLOY_NO_BUILD=1 -> bo qua buoc docker compose build."
  else
    log_info "Bat dau build image (co the mat vai phut)..."
    build_with_retry
  fi

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

main "$@"
