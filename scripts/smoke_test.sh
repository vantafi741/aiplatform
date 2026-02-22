#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# ==============================================================
# Smoke test nhanh sau deploy
# - Bat buoc: /api/healthz
# - Neu co: /api/readyz
# - OpenAPI: /openapi.json hoac /api/openapi.json
# - Optional docs: /docs (200/302 la OK)
# ==============================================================

readonly COLOR_RED="\033[0;31m"
readonly COLOR_GREEN="\033[0;32m"
readonly COLOR_YELLOW="\033[1;33m"
readonly COLOR_BLUE="\033[0;34m"
readonly COLOR_RESET="\033[0m"

TMP_FILE="$(mktemp)"
cleanup() {
  rm -f "${TMP_FILE}"
}
trap cleanup EXIT

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

http_code() {
  local url="$1"
  curl -sS -o "${TMP_FILE}" -w "%{http_code}" "${url}" || true
}

print_body_snippet() {
  if [[ -s "${TMP_FILE}" ]]; then
    echo "----- response body -----"
    sed -n '1,20p' "${TMP_FILE}"
    echo "-------------------------"
  fi
}

http_check_required() {
  local url="$1"
  local name="$2"
  local code
  code="$(http_code "${url}")"

  if [[ "${code}" =~ ^2[0-9]{2}$ ]]; then
    log_ok "${name} OK (${code}) -> ${url}"
    return 0
  fi

  log_fail "${name} FAIL (${code}) -> ${url}"
  print_body_snippet
  return 1
}

http_check_optional() {
  local url="$1"
  local name="$2"
  local code
  code="$(http_code "${url}")"

  if [[ "${code}" =~ ^2[0-9]{2}$ ]]; then
    log_ok "${name} OK (${code}) -> ${url}"
    return 0
  fi

  if [[ "${code}" == "404" ]]; then
    log_warn "${name} khong ton tai (404), bo qua."
    return 0
  fi

  log_fail "${name} FAIL (${code}) -> ${url}"
  print_body_snippet
  return 1
}

check_openapi_or_docs() {
  local base_url="$1"
  local code=""

  code="$(http_code "${base_url}/openapi.json")"
  if [[ "${code}" =~ ^2[0-9]{2}$ ]]; then
    log_ok "OpenAPI OK (${code}) -> ${base_url}/openapi.json"
    return 0
  fi

  code="$(http_code "${base_url}/api/openapi.json")"
  if [[ "${code}" =~ ^2[0-9]{2}$ ]]; then
    log_ok "OpenAPI OK (${code}) -> ${base_url}/api/openapi.json"
    return 0
  fi

  code="$(http_code "${base_url}/docs")"
  if [[ "${code}" =~ ^(200|302)$ ]]; then
    log_ok "Docs endpoint OK (${code}) -> ${base_url}/docs"
    return 0
  fi

  log_fail "Khong tim thay OpenAPI/docs endpoint hop le."
  print_body_snippet
  return 1
}

run_base_checks() {
  local base_url="$1"
  log_info "Smoke test tren base URL: ${base_url}"
  http_check_required "${base_url}/api/healthz" "healthz"
  http_check_optional "${base_url}/api/readyz" "readyz"
  check_openapi_or_docs "${base_url}"
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
