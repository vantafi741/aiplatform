"""
Shared logic for Meta scripts: repo root, deterministic env loading, mask, diagnosis.
Do not print full token/secret. Timeout 20s.
Exit codes: 2 missing env, 3 token invalid, 4 permission missing, 5 post fail.
"""
from pathlib import Path
import os
import re
import subprocess
import sys

try:
    import requests
except ImportError:
    requests = None

REQUIRED_META_KEYS = (
    "META_APP_ID",
    "META_APP_SECRET",
    "FACEBOOK_PAGE_ID",
    "FACEBOOK_PAGE_ACCESS_TOKEN",
)
OPTIONAL_META_KEYS = (
    "META_BUSINESS_ID",
    "META_SYSTEM_USER_ID",
    "WEBHOOK_VERIFY_TOKEN",
    "WEBHOOK_SECRET",
)
GRAPH_BASE = "https://graph.facebook.com/v24.0"
TIMEOUT = 20

EXIT_MISSING_ENV = 2
EXIT_TOKEN_INVALID = 3
EXIT_PERMISSION_MISSING = 4
EXIT_POST_FAIL = 5

REQUIRED_SCOPES_POST = ["pages_manage_posts", "pages_read_engagement"]
REQUIRED_SCOPES_ACCOUNTS = ["pages_show_list"]


def get_repo_root(anchor: Path) -> Path:
    """Resolve git repo root from anchor (e.g. script dir). Not cwd-dependent."""
    start = anchor if anchor.is_dir() else anchor.parent
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=start,
        )
        if p.returncode == 0 and p.stdout.strip():
            return Path(p.stdout.strip()).resolve()
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    for p in [start] + list(start.parents):
        if (p / ".git").exists():
            return p.resolve()
    return start.resolve()


def _normalize_for_compare(value: str, is_token_like: bool) -> str:
    """Normalize for env vs .env comparison; token-like keys use sanitize_token."""
    if not value:
        return ""
    s = str(value).strip()
    if is_token_like:
        out = sanitize_token(s)
        return out if out is not None else s
    return s


def load_env_deterministic(
    anchor: Path,
    required_keys: tuple,
    optional_keys: tuple,
) -> tuple:
    """
    Load .env from repo root (git root). Return (repo_root, env_path, env_dict, source_map).
    source_map[key]:
      - "env (preloaded, same as .env)" when process env had key and value equals .env
      - "env (overrides .env)" when process env had key and value differs from .env
      - ".env" when value came from file only
      - None when missing.
    """
    repo_root = get_repo_root(anchor)
    env_path = repo_root / ".env"

    all_keys = required_keys + optional_keys
    snapshot_before = {k: os.environ.get(k) for k in all_keys}

    file_values = {}
    try:
        from dotenv import load_dotenv
        try:
            from dotenv import dotenv_values
            file_values = dotenv_values(env_path) or {}
        except ImportError:
            pass
        load_dotenv(env_path)
    except ImportError:
        pass

    env_dict = {}
    source_map = {}
    for k in all_keys:
        v = os.environ.get(k)
        if v and str(v).strip():
            raw = str(v).strip()
            is_token_like = "TOKEN" in k or "SECRET" in k or "ACCESS" in k
            cleaned = sanitize_token(raw) if is_token_like else raw
            env_dict[k] = cleaned if (cleaned is not None) else raw
            if snapshot_before.get(k) and str(snapshot_before.get(k)).strip():
                env_before = (snapshot_before.get(k) or "").strip()
                norm_env = _normalize_for_compare(env_before, is_token_like)
                file_val = (file_values.get(k) or "").strip() if file_values.get(k) is not None else None
                if file_val is not None:
                    norm_file = _normalize_for_compare(file_val, is_token_like)
                    if norm_file == norm_env:
                        source_map[k] = "env (preloaded, same as .env)"
                    else:
                        source_map[k] = "env (overrides .env)"
                else:
                    source_map[k] = "env (overrides .env)"
            else:
                source_map[k] = ".env"
        else:
            source_map[k] = None

    return repo_root, env_path, env_dict, source_map


def sanitize_token(value: str):
    """
    Token shape sanity: trim, strip surrounding quotes, reject if empty or invalid.
    Returns cleaned string or None if invalid (caller may still use raw for error msg).
    """
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    if s.startswith('"') and s.endswith('"') and len(s) >= 2:
        s = s[1:-1].strip()
    elif s.startswith("'") and s.endswith("'") and len(s) >= 2:
        s = s[1:-1].strip()
    if not s:
        return None
    if re.search(r"[\s\x00-\x1f]", s):
        return None
    return s


def is_token_shape_valid(value: str) -> bool:
    """True if token passes shape sanity (trim, no invalid quotes/ws)."""
    return sanitize_token(value) is not None


def mask_secret(value: str) -> str:
    """6 chars + ... + 6 chars; if len < 13 then 2 + ... + 2. Never print full value."""
    if not value or not value.strip():
        return "(empty)"
    s = value.strip()
    if len(s) < 4:
        return "***"
    if len(s) < 13:
        return s[0:2] + "..." + s[-2:]
    return s[:6] + "..." + s[-6:]


def format_env_context(
    cwd: Path,
    repo_root: Path,
    env_path: Path,
    source_map: dict,
    env_dict: dict,
    required_keys: tuple,
    optional_keys: tuple,
    mask_keys: set,
) -> list:
    """Build lines for printing: cwd, repo_root, env_path always; then per-key value and source (incl. override)."""
    lines = [
        f"  cwd:       {cwd}",
        f"  repo_root: {repo_root}",
        f"  env_path:  {env_path}",
        "  sources:   (.env = file only; env (preloaded, same as .env) = process env matches .env; env (overrides .env) = process env differs from .env)",
    ]
    for k in required_keys + optional_keys:
        src = source_map.get(k)
        if src is None:
            lines.append(f"    {k}: (missing)  [source: -]")
        else:
            val = env_dict.get(k, "")
            if k in mask_keys:
                val = mask_secret(val) if val else "(empty)"
            lines.append(f"    {k}: {val}  [source: {src}]")
    return lines


def diagnosis_hints_403(
    token_type: str = None,
    page_id_env: str = None,
    page_id_token: str = None,
    has_required_scopes: bool = None,
    granular_scopes_not_covering_page: bool = None,
) -> list:
    """Return list of diagnosis hint strings for 403 (#200) post failure."""
    hints = [
        "  Diagnosis (403 #200):",
        "  - token is USER not PAGE -> use Page token or get from /me/accounts for FACEBOOK_PAGE_ID",
        "  - token not granted for this page_id -> ensure token is for the Page in .env",
        "  - user not admin/full control on page -> Page role must be Admin",
        "  - page not linked to app/business/system user -> link Page to App in Meta Business Suite",
        "  - granular scopes not covering this page_id -> in Business Suite grant task for this Page",
        "  - New Pages Experience task not granted -> grant MANAGE permission for the Page (New Pages Experience)",
    ]
    if token_type:
        hints.append(f"  (current token_type: {token_type})")
    if page_id_env and page_id_token and page_id_env != page_id_token:
        hints.append(f"  (env FACEBOOK_PAGE_ID={page_id_env} vs token page_id={page_id_token} -> mismatch)")
    if has_required_scopes is False:
        hints.append("  (missing required scopes: pages_manage_posts, pages_read_engagement)")
    if granular_scopes_not_covering_page:
        hints.append("  (granular_scopes do not include this page in target_ids)")
    return hints


def required_scopes_checklist(using_me_accounts: bool, token_type: str = None) -> list:
    """Required scopes for posting. pages_show_list only when using /me/accounts AND token_type is USER (not SYSTEM_USER)."""
    scopes = list(REQUIRED_SCOPES_POST)
    if using_me_accounts and (token_type or "").upper() == "USER":
        scopes.extend(REQUIRED_SCOPES_ACCOUNTS)
    return scopes


def get_identity(access_token: str) -> dict:
    """
    GET /me?fields=id,name with access_token. Returns {"id": ..., "name": ...} or {"error": "..."}.
    Uses TIMEOUT. Does not log or print token (caller must use mask_secret if logging).
    """
    if not requests:
        return {"error": "requests not installed"}
    url = f"{GRAPH_BASE}/me"
    params = {"fields": "id,name", "access_token": access_token}
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        data = r.json() if r.text else {}
        if "error" in data:
            return {"error": data["error"].get("message", str(data["error"]))}
        return {"id": data.get("id"), "name": data.get("name", "")}
    except requests.RequestException as e:
        return {"error": str(e)}


def verify_page_access(page_id: str, access_token: str) -> bool:
    """
    GET /{page_id}?fields=id,name with access_token. Returns True if 200 and no error in body.
    Uses TIMEOUT. Does not log token.
    """
    if not requests:
        return False
    url = f"{GRAPH_BASE}/{page_id}"
    params = {"fields": "id,name", "access_token": access_token}
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        if not r.ok:
            return False
        data = r.json() if r.text else {}
        return "error" not in data
    except requests.RequestException:
        return False
