"""
Meta/Facebook token verification: token type (USER vs PAGE), page binding, scopes checklist.
Deterministic env from repo root. Exit 2 missing env, 3 token invalid, 4 permission missing.
Prints granular_scopes when present. Only calls /me/accounts for USER/SYSTEM_USER; PAGE => skip.
Fallback: GET /{PAGE_ID}?fields=access_token if /me/accounts fails. Timeout 20s. Never print full token.
"""
from pathlib import Path
import os
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from _meta_common import (
    get_repo_root,
    load_env_deterministic,
    mask_secret,
    format_env_context,
    diagnosis_hints_403,
    required_scopes_checklist,
    is_token_shape_valid,
    sanitize_token,
    get_identity,
    verify_page_access,
    REQUIRED_META_KEYS,
    GRAPH_BASE,
    TIMEOUT,
    EXIT_MISSING_ENV,
    EXIT_TOKEN_INVALID,
    EXIT_PERMISSION_MISSING,
)
MASK_KEYS = {k for k in REQUIRED_META_KEYS if "SECRET" in k or "TOKEN" in k or "ACCESS" in k}

import requests

FORMAT_MODE = os.environ.get("FORMAT_MODE", "COMPACT").strip().upper()
SEP = "" if FORMAT_MODE == "PRETTY" else ""


def get_env() -> dict:
    cwd = Path.cwd()
    repo_root, env_path, env_dict, source_map = load_env_deterministic(
        SCRIPT_DIR, REQUIRED_META_KEYS, ()
    )
    missing = [k for k in REQUIRED_META_KEYS if k not in env_dict or not env_dict[k]]
    if missing:
        lines = [
            "[ERROR] Thieu bien moi truong: " + ", ".join(missing),
            "Chay tu repo root de load .env:  cd " + str(repo_root),
            "Chay: python scripts/meta_env_doctor.py de xem huong dan.",
        ]
        print(SEP.join(lines) if SEP else "".join(lines))
        sys.exit(EXIT_MISSING_ENV)
    if not is_token_shape_valid(env_dict.get("FACEBOOK_PAGE_ACCESS_TOKEN", "")):
        print("[ERROR] FACEBOOK_PAGE_ACCESS_TOKEN co hinh dang khong hop le (quotes/wspace).")
        sys.exit(EXIT_TOKEN_INVALID)
    if not is_token_shape_valid(env_dict.get("META_APP_SECRET", "")):
        print("[ERROR] META_APP_SECRET co hinh dang khong hop le (quotes/wspace).")
        sys.exit(EXIT_TOKEN_INVALID)
    return env_dict


def debug_token(app_id: str, app_secret: str, token: str) -> dict:
    url = f"{GRAPH_BASE}/debug_token"
    params = {"input_token": token, "access_token": f"{app_id}|{app_secret}"}
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("data", {})
    except requests.RequestException as e:
        return {"error": str(e), "is_valid": False}


def main() -> int:
    env = get_env()
    app_id = env["META_APP_ID"]
    app_secret = env["META_APP_SECRET"]
    page_id_env = env["FACEBOOK_PAGE_ID"]
    page_token = env["FACEBOOK_PAGE_ACCESS_TOKEN"]
    page_token = sanitize_token(page_token) or page_token

    cwd = Path.cwd()
    repo_root, env_path, _, source_map = load_env_deterministic(SCRIPT_DIR, REQUIRED_META_KEYS, ())
    context_lines = format_env_context(
        cwd, repo_root, env_path, source_map, env,
        REQUIRED_META_KEYS, (), MASK_KEYS
    )

    parts = ["Env context:"]
    parts.extend(context_lines)
    parts.append("-" * 60)

    me_url = f"{GRAPH_BASE}/me"
    me_params = {"fields": "id,name", "access_token": page_token}
    me_id = me_name = None
    try:
        me_resp = requests.get(me_url, params=me_params, timeout=TIMEOUT)
        me_data = me_resp.json() if me_resp.ok else {}
        if "error" in me_data:
            parts.append("[FAIL] /me: " + str(me_data["error"].get("message", me_data["error"])))
        else:
            me_id = me_data.get("id")
            me_name = me_data.get("name", "")
            parts.append(f"[OK] /me: id={me_id}, name={me_name}")
    except requests.RequestException as e:
        parts.append(f"[FAIL] /me: {e}")

    debug = debug_token(app_id, app_secret, page_token)
    valid = debug.get("is_valid", False)
    token_type = (debug.get("type") or "unknown").upper()
    app_id_debug = debug.get("app_id", "")
    expires_at = debug.get("expires_at")
    scopes = debug.get("scopes", [])
    granular_scopes = debug.get("granular_scopes", [])
    if expires_at is None:
        exp_str = "(unknown)"
    elif expires_at == 0:
        exp_str = "never"
    elif isinstance(expires_at, int) and expires_at > 0:
        from datetime import datetime
        exp_str = datetime.utcfromtimestamp(expires_at).isoformat() + "Z"
    else:
        exp_str = "never"

    used_me_accounts = False
    token_page_id = None
    if token_type in ("PAGE", "PAGE_ACCESS_TOKEN") and me_id:
        token_page_id = str(me_id)
        page_ok = verify_page_access(page_id_env, page_token)
        if page_ok:
            token_page_id = str(page_id_env)
        else:
            identity = get_identity(page_token)
            parts.append("binding_mismatch: token maps to id=%s, name=%s (expected page %s)" % (
                identity.get("id", "?"), identity.get("name", "?"), page_id_env))
            parts.append("  -> Grant Page task for FACEBOOK_PAGE_ID or use token for that Page.")
    elif token_type in ("USER", "SYSTEM_USER"):
        acc_url = f"{GRAPH_BASE}/me/accounts"
        acc_params = {"fields": "id,name,access_token", "access_token": page_token}
        try:
            acc_resp = requests.get(acc_url, params=acc_params, timeout=TIMEOUT)
            acc_data = acc_resp.json() if acc_resp.ok else {}
            if "data" in acc_data and acc_data["data"]:
                used_me_accounts = True
                for p in acc_data["data"]:
                    if str(p.get("id")) == str(page_id_env):
                        page_token = p.get("access_token", "")
                        token_page_id = str(p.get("id"))
                        parts.append(f"[OK] Page token from /me/accounts for FACEBOOK_PAGE_ID={page_id_env}")
                        break
                if not token_page_id:
                    token_page_id = "n/a"
                    parts.append(f"[WARN] FACEBOOK_PAGE_ID={page_id_env} not in /me/accounts; token not for this page")
                else:
                    page_ok = verify_page_access(page_id_env, page_token)
                    parts.append("page_access_check: OK" if page_ok else "page_access_check: FAIL")
                    if not page_ok:
                        parts.append("  -> Grant Page task/permissions for this Page in Business Suite.")
            else:
                err = acc_data.get("error", {})
                parts.append(f"[WARN] /me/accounts: " + str(err.get("message", err)))
                fallback_url = f"{GRAPH_BASE}/{page_id_env}"
                fallback_params = {"fields": "access_token", "access_token": page_token}
                try:
                    fb = requests.get(fallback_url, params=fallback_params, timeout=TIMEOUT)
                    fb_data = fb.json() if fb.ok else {}
                    if "access_token" in fb_data and fb_data.get("access_token"):
                        page_token = fb_data["access_token"]
                        token_page_id = page_id_env
                        parts.append(f"[OK] Page token from fallback GET /{page_id_env}?fields=access_token")
                        page_ok = verify_page_access(page_id_env, page_token)
                        parts.append("page_access_check: OK" if page_ok else "page_access_check: FAIL")
                        if not page_ok:
                            parts.append("  -> Grant Page task/permissions for this Page in Business Suite.")
                except requests.RequestException:
                    pass
        except requests.RequestException as e:
            parts.append(f"[WARN] /me/accounts: {e}")
            fallback_url = f"{GRAPH_BASE}/{page_id_env}"
            fallback_params = {"fields": "access_token", "access_token": page_token}
            try:
                fb = requests.get(fallback_url, params=fallback_params, timeout=TIMEOUT)
                fb_data = fb.json() if fb.ok else {}
                if "access_token" in fb_data and fb_data.get("access_token"):
                    page_token = fb_data["access_token"]
                    token_page_id = page_id_env
                    parts.append(f"[OK] Page token from fallback GET /{page_id_env}?fields=access_token")
                    page_ok = verify_page_access(page_id_env, page_token)
                    parts.append("page_access_check: OK" if page_ok else "page_access_check: FAIL")
                    if not page_ok:
                        parts.append("  -> Grant Page task/permissions for this Page in Business Suite.")
            except requests.RequestException:
                pass
    else:
        token_page_id = str(me_id) if me_id else None

    page_url = f"{GRAPH_BASE}/{page_id_env}"
    page_params = {"fields": "id,name,link,fan_count", "access_token": page_token}
    try:
        page_resp = requests.get(page_url, params=page_params, timeout=TIMEOUT)
        page_data = page_resp.json() if page_resp.ok else {}
        if "error" in page_data:
            parts.append(f"[FAIL] /{page_id_env}: " + str(page_data["error"].get("message", page_data["error"])))
        else:
            pi = page_data
            parts.append(f"[OK] Page: id={pi.get('id')}, name={pi.get('name')}, link={pi.get('link')}, fan_count={pi.get('fan_count')}")
    except requests.RequestException as e:
        parts.append(f"[FAIL] Page request: {e}")

    parts.append("Ket qua debug_token:")
    parts.append("-" * 60)
    parts.append(f"  token_valid:  {valid}")
    parts.append(f"  token_type:   {token_type}")
    parts.append(f"  app_id:       {app_id_debug}")
    parts.append(f"  expires_at:   {exp_str}")
    parts.append(f"  scopes:       {', '.join(scopes) if scopes else '(empty)'}")
    if granular_scopes:
        for g in granular_scopes:
            scope_name = g.get("scope", "")
            target_ids = g.get("target_ids", [])
            parts.append(f"  granular_scopes: scope={scope_name} target_ids={target_ids}")
    required = required_scopes_checklist(used_me_accounts, token_type)
    have = [s for s in required if s in scopes]
    missing_scopes = [s for s in required if s not in scopes]
    parts.append(f"  required:     {required}")
    parts.append(f"  have:         {have}")
    if missing_scopes:
        parts.append(f"  missing:      {missing_scopes}")
    parts.append(f"  FACEBOOK_PAGE_ID (env):  {page_id_env}")
    parts.append(f"  page_id (token):         {token_page_id or 'n/a'}")
    parts.append("-" * 60)

    granular_not_covering = False
    if granular_scopes and page_id_env:
        page_str = str(page_id_env)
        for g in granular_scopes:
            target_ids = [str(t) for t in (g.get("target_ids") or [])]
            if target_ids and page_str not in target_ids:
                granular_not_covering = True
                break

    if not valid:
        parts.extend(diagnosis_hints_403(
            token_type=token_type,
            page_id_env=page_id_env,
            page_id_token=token_page_id,
            has_required_scopes=len(missing_scopes) == 0,
            granular_scopes_not_covering_page=granular_not_covering,
        ))
        print(SEP.join(parts) if SEP else "".join(parts))
        sys.exit(EXIT_TOKEN_INVALID)
    if token_page_id and str(token_page_id) != str(page_id_env):
        parts.extend(diagnosis_hints_403(
            token_type=token_type,
            page_id_env=page_id_env,
            page_id_token=token_page_id,
            has_required_scopes=len(missing_scopes) == 0,
            granular_scopes_not_covering_page=granular_not_covering,
        ))
        print(SEP.join(parts) if SEP else "".join(parts))
        sys.exit(EXIT_PERMISSION_MISSING)
    if missing_scopes and not (used_me_accounts and str(token_page_id) == str(page_id_env)):
        parts.extend(diagnosis_hints_403(
            token_type=token_type,
            has_required_scopes=False,
            granular_scopes_not_covering_page=granular_not_covering,
        ))
        print(SEP.join(parts) if SEP else "".join(parts))
        sys.exit(EXIT_PERMISSION_MISSING)

    parts.append("[OK] Token hop le. Co the chay: python scripts/meta_post_test.py --message \"Test\"")
    print(SEP.join(parts) if SEP else "".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
