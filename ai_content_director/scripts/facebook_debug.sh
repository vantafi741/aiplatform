#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

GRAPH_BASE="https://graph.facebook.com/v19.0"
PAGE_ID="${FACEBOOK_PAGE_ID:-}"
TOKEN="${FB_PAGE_ACCESS_TOKEN:-${FACEBOOK_ACCESS_TOKEN:-}}"
APP_ID="${FACEBOOK_APP_ID:-${APP_ID:-}}"
APP_SECRET="${FACEBOOK_APP_SECRET:-${APP_SECRET:-}}"
DRY_RUN="${DRY_RUN:-1}"

if [[ -z "${PAGE_ID}" ]]; then
  echo "[FAIL] Missing env FACEBOOK_PAGE_ID."
  exit 1
fi
if [[ -z "${TOKEN}" ]]; then
  echo "[FAIL] Missing token env FB_PAGE_ACCESS_TOKEN or FACEBOOK_ACCESS_TOKEN."
  exit 1
fi

token_len=${#TOKEN}
if (( token_len >= 12 )); then
  token_prefix="${TOKEN:0:12}"
else
  token_prefix="${TOKEN}"
fi

echo "== Facebook Debug =="
echo "PAGE_ID: ${PAGE_ID}"
echo "TOKEN_LEN: ${token_len}"
echo "TOKEN_PREFIX: ${token_prefix}..."
echo "DRY_RUN: ${DRY_RUN}"
echo

graph_get() {
  local endpoint="$1"
  shift
  curl -sS --get "${GRAPH_BASE}/${endpoint}" "$@" --data-urlencode "access_token=${TOKEN}"
}

graph_post() {
  local endpoint="$1"
  shift
  curl -sS -X POST "${GRAPH_BASE}/${endpoint}" "$@" --data-urlencode "access_token=${TOKEN}"
}

json_has_error() {
  local json_input="$1"
  python -c "import json,sys; d=json.loads(sys.stdin.read() or '{}'); print('1' if isinstance(d, dict) and isinstance(d.get('error'), dict) else '0')" <<< "${json_input}" 2>/dev/null || echo "0"
}

json_read() {
  local json_input="$1"
  local expr="$2"
  python -c "import json,sys; d=json.loads(sys.stdin.read() or '{}'); v=(${expr}); print('' if v is None else v)" <<< "${json_input}" 2>/dev/null || true
}

print_error_hint() {
  local json_input="$1"
  local code
  local subcode
  local message
  code="$(json_read "${json_input}" "d.get('error', {}).get('code')")"
  subcode="$(json_read "${json_input}" "d.get('error', {}).get('error_subcode')")"
  message="$(json_read "${json_input}" "d.get('error', {}).get('message')")"

  echo "  ERROR: code=${code:-n/a} subcode=${subcode:-n/a} message=${message:-n/a}"
  if [[ "${code}" == "10" && "${subcode}" == "2069007" ]]; then
    echo "  HINT: Missing publish permission. Ensure pages_manage_posts/pages_read_engagement/pages_show_list,"
    echo "        then generate USER token -> exchange PAGE token via /me/accounts and verify CREATE_CONTENT task."
  fi
}

print_check_result() {
  local title="$1"
  local resp="$2"

  echo "- ${title}"
  if [[ "$(json_has_error "${resp}")" == "1" ]]; then
    print_error_hint "${resp}"
  else
    echo "  OK: ${resp}"
  fi
}

page_info="$(graph_get "${PAGE_ID}" --data-urlencode "fields=id,name")"
me_info="$(graph_get "me" --data-urlencode "fields=id,name")"

echo "== Graph Checks =="
print_check_result "GET /${PAGE_ID}?fields=id,name" "${page_info}"
print_check_result "GET /me?fields=id,name" "${me_info}"

echo
echo "== Publish Check =="
if [[ "${DRY_RUN}" == "1" ]]; then
  echo "DRY_RUN=1, skip POST /${PAGE_ID}/feed"
  echo "Preview command:"
  echo "curl -sS -X POST \"${GRAPH_BASE}/${PAGE_ID}/feed\" --data-urlencode \"message=Debug post from facebook_debug.sh\" --data-urlencode \"access_token=<REDACTED>\""
else
  post_message="Debug post from facebook_debug.sh at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  feed_resp="$(graph_post "${PAGE_ID}/feed" --data-urlencode "message=${post_message}")"
  print_check_result "POST /${PAGE_ID}/feed" "${feed_resp}"
fi

echo
echo "== debug_token (optional) =="
if [[ -n "${APP_ID}" && -n "${APP_SECRET}" ]]; then
  app_token="${APP_ID}|${APP_SECRET}"
  debug_resp="$(curl -sS --get "${GRAPH_BASE}/debug_token" --data-urlencode "input_token=${TOKEN}" --data-urlencode "access_token=${app_token}")"
  if [[ "$(json_has_error "${debug_resp}")" == "1" ]]; then
    print_error_hint "${debug_resp}"
  else
    echo "type: $(json_read "${debug_resp}" "d.get('data', {}).get('type')")"
    echo "is_valid: $(json_read "${debug_resp}" "d.get('data', {}).get('is_valid')")"
    echo "expires_at: $(json_read "${debug_resp}" "d.get('data', {}).get('expires_at')")"
    echo "scopes: $(json_read "${debug_resp}" "d.get('data', {}).get('scopes')")"
    echo "application: $(json_read "${debug_resp}" "d.get('data', {}).get('application')")"
  fi
else
  echo "Skip /debug_token (set FACEBOOK_APP_ID and FACEBOOK_APP_SECRET)."
fi

echo
echo "[DONE] facebook_debug completed."
