#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

# Scan repo for potential secrets without printing secret contents.
# Usage:
#   bash scripts/check_secrets_in_repo.sh

REPO_ROOT="${REPO_ROOT:-$(pwd)}"
REPORT_FILE="${REPORT_FILE:-${REPO_ROOT}/docs/SECRETS_SCAN_REPORT.md}"
cd "${REPO_ROOT}"

mkdir -p "$(dirname "${REPORT_FILE}")"
{
  echo "# Secrets Scan Report"
  echo
  echo "- generated_at: $(date -Iseconds 2>/dev/null || date)"
  echo "- repo_root: ${REPO_ROOT}"
  echo
} > "${REPORT_FILE}"

log() {
  echo "$1"
  echo "$1" >> "${REPORT_FILE}"
}

log "[INFO] Secret scan started at: ${REPO_ROOT}"

has_issue=0

if command -v rg >/dev/null 2>&1; then
  SEARCH_CMD="rg"
else
  SEARCH_CMD="grep"
  log "[WARN] ripgrep (rg) not found, fallback to grep."
fi

check_pattern_files_only() {
  local label="$1"
  local pattern="$2"
  local files
  if [ "${SEARCH_CMD}" = "rg" ]; then
    files="$(rg --files-with-matches --hidden --no-ignore-vcs \
      --glob '!**/.git/**' \
      --glob '!**/.venv/**' \
      --glob '!**/node_modules/**' \
      --glob '!**/dist/**' \
      --glob '!**/.env' \
      --glob '!**/.env.local' \
      --glob '!**/.env.prod' \
      --glob '!**/secrets/**' \
      --glob '!**/*.env.example' \
      --glob '!**/.env.example' \
      "${pattern}" . || true)"
  else
    files="$(grep -R -l -E "${pattern}" . \
      --exclude-dir=.git \
      --exclude-dir=.venv \
      --exclude-dir=node_modules \
      --exclude-dir=dist \
      --exclude='.env' \
      --exclude='.env.local' \
      --exclude='.env.prod' \
      --exclude='*.env.example' \
      --exclude='.env.example' 2>/dev/null || true)"
  fi
  if [ -n "${files}" ]; then
    has_issue=1
    log "[WARN] ${label}: possible matches found"
    echo "${files}" | tee -a "${REPORT_FILE}"
  fi
}

check_tracked_sensitive_files() {
  # File names that should never be tracked.
  local tracked
  if [ "${SEARCH_CMD}" = "rg" ]; then
    tracked="$(git ls-files | rg "(\.env$|\.env\.local$|\.env\.prod$|id_rsa|\.pem$|service-account.*\.json$|credentials.*\.json$|secret.*\.json$)" || true)"
  else
    tracked="$(git ls-files | grep -E "(\.env$|\.env\.local$|\.env\.prod$|id_rsa|\.pem$|service-account.*\.json$|credentials.*\.json$|secret.*\.json$)" || true)"
  fi
  if [ -n "${tracked}" ]; then
    has_issue=1
    log "[WARN] Sensitive files are tracked in git:"
    echo "${tracked}" | tee -a "${REPORT_FILE}"
  fi
}

check_history_risk_warning() {
  # Do not rewrite history automatically. Only warn.
  local commits
  if [ "${SEARCH_CMD}" = "rg" ]; then
    commits="$(git rev-list --all -- ".env" ".env.local" ".env.prod" "*service-account*.json" "*.pem" 2>/dev/null | rg ".+" || true)"
  else
    commits="$(git rev-list --all -- ".env" ".env.local" ".env.prod" "*service-account*.json" "*.pem" 2>/dev/null | grep -E ".+" || true)"
  fi
  if [ -n "${commits}" ]; then
    log "[WARN] Potential secret exposure risk in commit history detected."
    log "[WARN] Action: manual audit + rotate keys. Do NOT rewrite history unless explicitly approved."
  fi
}

check_tracked_sensitive_files

# Common token/key shapes (file list only, no value output)
check_pattern_files_only "OpenAI key pattern" "sk-[A-Za-z0-9]{20,}"
check_pattern_files_only "Google API key pattern" "AIza[0-9A-Za-z\\-_]{20,}"
check_pattern_files_only "Facebook token assignment" "(FACEBOOK_ACCESS_TOKEN|FB_PAGE_ACCESS_TOKEN)\\s*=\\s*[A-Za-z0-9_\\-]{24,}"
check_pattern_files_only "Private key block" "-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----"
check_pattern_files_only "Generic high-risk assignment" "(API_KEY|SECRET|TOKEN|PASSWORD)\\s*=\\s*[A-Za-z0-9_\\-\\./\\+=]{24,}"

check_history_risk_warning

if [ "${has_issue}" -eq 1 ]; then
  log "[FAIL] Potential secrets found. Review warnings above."
  exit 2
fi

log "[OK] No obvious secrets detected in current workspace scan."
