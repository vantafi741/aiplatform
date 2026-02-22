#!/usr/bin/env bash
set -euo pipefail

# ==============================================================
# Smoke test nhanh sau deploy
# - Bat buoc: /api/healthz
# - Neu co: /api/readyz
# - OpenAPI: /openapi.json hoac /api/openapi.json
# ==============================================================

readonly COLOR_RED="\033[0;31m"
readonly COLOR_GREEN="\033[0;32m"
readonly COLOR_YELLOW="\033[1;33m"
readonly COLOR_BLUE="\033[0;34m"
readonly COLOR_RESET="\033[0m"

log_info() {
  echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} $*"
}

log_ok() {
  echo -e "${COLOR_GREEN}[OK]${COLOR_RESET} $*"
}

log_warn() {
  echo -e "${COLOR_YELLOW}[WARN]${COLOR_RESET} $*"
}

log_fail() {
  echo -e "${COLOR_RED}[FAIL]${COLOR_RESET} $*"
}

http_check_required() {
  local url="$1"
  local name="$2"
  local code
  code="$(curl -sS -o /tmp/smoke_response_body.txt -w "%{http_code}" "${url}" || true)"
  if [[ "${code}" =~ ^2[0-9]{2}$ ]]; then
    log_ok "${name} OK (${code}) -> ${url}"
    return 0
  fi

  log_fail "${name} FAIL (${code}) -> ${url}"
  if [[ -s /tmp/smoke_response_body.txt ]]; then
    echo "----- response body (${name}) -----"
    sed -n '1,20p' /tmp/smoke_response_body.txt
    echo "-----------------------------------"
  fi
  return 1
}

http_check_optional() {
  local url="$1"
  local name="$2"
  local code
  code="$(curl -sS -o /tmp/smoke_response_body.txt -w "%{http_code}" "${url}" || true)"
  if [[ "${code}" =~ ^2[0-9]{2}$ ]]; then
    log_ok "${name} OK (${code}) -> ${url}"
    return 0
  fi

  if [[ "${code}" == "404" ]]; then
    log_warn "${name} khong ton tai (404), bo qua."
    return 0
  fi

  log_fail "${name} FAIL (${code}) -> ${url}"
  if [[ -s /tmp/smoke_response_body.txt ]]; then
    echo "----- response body (${name}) -----"
    sed -n '1,20p' /tmp/smoke_response_body.txt
    echo "-----------------------------------"
  fi
  return 1
}

check_openapi() {
  local base_url="$1"
  if curl -fsS "${base_url}/openapi.json" >/dev/null 2>&1; then
    log_ok "OpenAPI OK -> ${base_url}/openapi.json"
    return 0
  fi
  if curl -fsS "${base_url}/api/openapi.json" >/dev/null 2>&1; then
    log_ok "OpenAPI OK -> ${base_url}/api/openapi.json"
    return 0
  fi
  log_fail "Khong tim thay OpenAPI endpoint hop le."
  return 1
}

run_base_checks() {
  local base_url="$1"
  log_info "Smoke test tren base URL: ${base_url}"
  http_check_required "${base_url}/api/healthz" "healthz"
  http_check_optional "${base_url}/api/readyz" "readyz"
  check_openapi "${base_url}"
}

main() {
  local base_url="${API_BASE_URL:-http://localhost:8000}"

  run_base_checks "${base_url}"

  # Optional staging port: test them neu user bat cho moi truong staging.
  if [[ "${SMOKE_TEST_STAGING_8001:-0}" == "1" ]]; then
    local staging_url="${STAGING_API_BASE_URL:-http://localhost:8001}"
    log_info "Bat kiem tra them cho staging: ${staging_url}"
    run_base_checks "${staging_url}"
  fi

  echo -e "${COLOR_GREEN}✅ SMOKE TEST SUCCESS${COLOR_RESET}"
}

if ! main "$@"; then
  echo -e "${COLOR_RED}❌ SMOKE TEST FAILED${COLOR_RESET}"
  exit 1
fi
