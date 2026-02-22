#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

GRAPH_BASE="https://graph.facebook.com/v19.0"
TOKEN="${FB_PAGE_ACCESS_TOKEN:-${FACEBOOK_ACCESS_TOKEN:-}}"
PAGE_ID="${FACEBOOK_PAGE_ID:-}"
APP_ID="${APP_ID:-}"
APP_SECRET="${APP_SECRET:-}"

if [[ -z "${TOKEN}" ]]; then
  echo "[FAIL] Missing token. Set FB_PAGE_ACCESS_TOKEN or FACEBOOK_ACCESS_TOKEN."
  exit 1
fi
if [[ -z "${PAGE_ID}" ]]; then
  echo "[FAIL] Missing FACEBOOK_PAGE_ID."
  exit 1
fi

token_len=${#TOKEN}
token_prefix="${TOKEN:0:12}"

echo "== Facebook Debug =="
echo "PAGE_ID: ${PAGE_ID}"
echo "token_len: ${token_len}"
echo "token_prefix: ${token_prefix}..."
echo

call_graph() {
  local url="$1"
  shift
  curl -sS --get "${url}" "$@" --data-urlencode "access_token=${TOKEN}"
}

extract_json_value() {
  local json_input="$1"
  local py_expr="$2"
  python -c "import json,sys; d=json.loads(sys.stdin.read()); print(${py_expr})" <<< "${json_input}" 2>/dev/null || true
}

has_graph_error() {
  local json_input="$1"
  python -c "import json,sys; d=json.loads(sys.stdin.read()); print('1' if isinstance(d,dict) and 'error' in d else '0')" <<< "${json_input}" 2>/dev/null || echo "0"
}

print_graph_error() {
  local json_input="$1"
  python -c "import json,sys; d=json.loads(sys.stdin.read()); e=d.get('error',{}); print(f\"code={e.get('code')} subcode={e.get('error_subcode')} type={e.get('type')} message={e.get('message')}\")" <<< "${json_input}" 2>/dev/null || true
}

page_info="$(call_graph "${GRAPH_BASE}/${PAGE_ID}" --data-urlencode "fields=id,name")"
page_tasks="$(call_graph "${GRAPH_BASE}/${PAGE_ID}" --data-urlencode "fields=tasks")"
me_info="$(call_graph "${GRAPH_BASE}/me" --data-urlencode "fields=id,name")"

echo "== Raw Checks =="
echo "- GET /${PAGE_ID}?fields=id,name"
if [[ "$(has_graph_error "${page_info}")" == "1" ]]; then
  echo "  FAIL: $(print_graph_error "${page_info}")"
else
  echo "  OK: id=$(extract_json_value "${page_info}" "d.get('id')") name=$(extract_json_value "${page_info}" "d.get('name')")"
fi

echo "- GET /${PAGE_ID}?fields=tasks"
if [[ "$(has_graph_error "${page_tasks}")" == "1" ]]; then
  echo "  FAIL/UNSUPPORTED: $(print_graph_error "${page_tasks}")"
else
  echo "  OK: tasks=$(extract_json_value "${page_tasks}" "d.get('tasks')")"
fi

echo "- GET /me?fields=id,name"
if [[ "$(has_graph_error "${me_info}")" == "1" ]]; then
  echo "  FAIL: $(print_graph_error "${me_info}")"
else
  echo "  OK: id=$(extract_json_value "${me_info}" "d.get('id')") name=$(extract_json_value "${me_info}" "d.get('name')")"
fi

echo
echo "== Token Type Heuristic =="
me_id="$(extract_json_value "${me_info}" "d.get('id')")"
if [[ -n "${me_id}" && "${me_id}" == "${PAGE_ID}" ]]; then
  echo "Detected: looks like PAGE token (/me id == PAGE_ID)"
elif [[ -n "${me_id}" ]]; then
  echo "Detected: looks like USER token (/me id != PAGE_ID)"
else
  echo "Detected: unknown (cannot read /me)"
fi

if [[ -n "${APP_ID}" && -n "${APP_SECRET}" ]]; then
  echo
  echo "== /debug_token =="
  app_token="${APP_ID}|${APP_SECRET}"
  debug_resp="$(curl -sS --get "${GRAPH_BASE}/debug_token" --data-urlencode "input_token=${TOKEN}" --data-urlencode "access_token=${app_token}")"
  if [[ "$(has_graph_error "${debug_resp}")" == "1" ]]; then
    echo "debug_token FAIL: $(print_graph_error "${debug_resp}")"
  else
    echo "issued_to: $(extract_json_value "${debug_resp}" "d.get('data',{}).get('application')")"
    echo "type: $(extract_json_value "${debug_resp}" "d.get('data',{}).get('type')")"
    echo "is_valid: $(extract_json_value "${debug_resp}" "d.get('data',{}).get('is_valid')")"
    echo "expires_at: $(extract_json_value "${debug_resp}" "d.get('data',{}).get('expires_at')")"
    echo "scopes: $(extract_json_value "${debug_resp}" "d.get('data',{}).get('scopes')")"
  fi
else
  echo
  echo "== /debug_token =="
  echo "Skip (set APP_ID and APP_SECRET to enable deep token debug)"
fi

echo
echo "== Permission Diagnosis =="
echo "Required perms for publish flow:"
echo "- pages_manage_posts"
echo "- pages_read_engagement"
echo "- pages_show_list"
echo
echo "If publish fails with OAuthException code=10 subcode=2069007:"
echo "1) Add Facebook Login product in Meta app."
echo "2) Request/approve pages_manage_posts, pages_read_engagement, pages_show_list."
echo "3) Generate USER token with those scopes, then exchange PAGE token via /me/accounts."
echo "4) Ensure your Facebook user has Page task CREATE_CONTENT."
echo "5) Put PAGE token into FB_PAGE_ACCESS_TOKEN (or FACEBOOK_ACCESS_TOKEN), restart API."
echo
echo "[DONE] facebook_debug completed."
