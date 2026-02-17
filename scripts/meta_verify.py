"""
Meta/Facebook token verification: kiem tra token hop le, lay Page info, debug token.
FORMAT_MODE=COMPACT (default): no newline between blocks. FORMAT_MODE=PRETTY: newlines.
Timeout 20s. Never print full token. Chay: python scripts/meta_verify.py
"""
from pathlib import Path
import os
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

import requests

FORMAT_MODE = os.environ.get("FORMAT_MODE", "COMPACT").strip().upper()
SEP = "" if FORMAT_MODE == "COMPACT" else "\n"
GRAPH_BASE = "https://graph.facebook.com/v24.0"
TIMEOUT = 20

REQUIRED_KEYS = (
    "META_APP_ID",
    "META_APP_SECRET",
    "FACEBOOK_PAGE_ID",
    "FACEBOOK_PAGE_ACCESS_TOKEN",
)


def mask_secret(value: str) -> str:
    """6 chars + ... + 6 chars; if len < 13 then 2 + ... + 2."""
    if not value or not value.strip():
        return "(empty)"
    s = value.strip()
    if len(s) < 4:
        return "***"
    if len(s) < 13:
        return s[0:2] + "..." + s[-2:]
    return s[:6] + "..." + s[-6:]


def get_env() -> dict:
    env = {}
    missing = []
    for key in REQUIRED_KEYS:
        val = os.environ.get(key)
        if not val or not str(val).strip():
            missing.append(key)
        else:
            env[key] = val.strip()
    if missing:
        msg = f"[ERROR] Thieu bien moi truong: {', '.join(missing)}" + "Chay: python scripts/meta_env_doctor.py de xem huong dan."
        if FORMAT_MODE == "PRETTY":
            msg = f"[ERROR] Thieu bien moi truong: {', '.join(missing)}\nChay: python scripts/meta_env_doctor.py de xem huong dan."
        print(msg)
        sys.exit(1)
    return env


def debug_token(app_id: str, app_secret: str, page_token: str) -> dict:
    url = f"{GRAPH_BASE}/debug_token"
    params = {
        "input_token": page_token,
        "access_token": f"{app_id}|{app_secret}",
    }
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return data.get("data", {})
    except requests.RequestException as e:
        return {"error": str(e), "is_valid": False}


def main() -> int:
    env = get_env()
    app_id = env["META_APP_ID"]
    app_secret = env["META_APP_SECRET"]
    page_id = env["FACEBOOK_PAGE_ID"]
    page_token = env["FACEBOOK_PAGE_ACCESS_TOKEN"]

    parts = []

    me_url = f"{GRAPH_BASE}/me"
    me_params = {"fields": "id,name", "access_token": page_token}
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

    page_url = f"{GRAPH_BASE}/{page_id}"
    page_params = {"fields": "id,name,link,fan_count", "access_token": page_token}
    try:
        page_resp = requests.get(page_url, params=page_params, timeout=TIMEOUT)
        page_data = page_resp.json() if page_resp.ok else {}
        if "error" in page_data:
            parts.append(f"[FAIL] /{page_id}: " + str(page_data["error"].get("message", page_data["error"])))
        else:
            pi = page_data
            parts.append(f"[OK] Page: id={pi.get('id')}, name={pi.get('name')}, link={pi.get('link')}, fan_count={pi.get('fan_count')}")
    except requests.RequestException as e:
        parts.append(f"[FAIL] Page request: {e}")

    debug = debug_token(app_id, app_secret, page_token)
    valid = debug.get("is_valid", False)
    app_id_debug = debug.get("app_id", "")
    expires_at = debug.get("expires_at")
    scopes = debug.get("scopes", [])
    if expires_at is None:
        exp_str = "(unknown)"
    elif expires_at == 0:
        exp_str = "never"
    elif isinstance(expires_at, int) and expires_at > 0:
        from datetime import datetime
        exp_str = datetime.utcfromtimestamp(expires_at).isoformat() + "Z"
    else:
        exp_str = "never"

    parts.append("Ket qua debug_token:")
    parts.append("-" * 60)
    parts.append(f"  token_valid:  {valid}")
    parts.append(f"  app_id:       {app_id_debug}")
    parts.append(f"  expires_at:   {exp_str}")
    parts.append(f"  scopes:       {', '.join(scopes) if scopes else '(empty)'}")
    parts.append("-" * 60)

    if not valid:
        err = debug.get("error") or debug.get("message")
        parts.append("[Token khong hop le]")
        if err:
            parts.append(f"  Chi tiet: {err}")
        parts.append("  Huong dan: Tao lai Page Access Token hoac System User token; quyen pages_manage_posts, pages_read_engagement")
        print(SEP.join(parts))
        return 1

    parts.append("[OK] Token hop le. Co the chay: python scripts/meta_post_test.py --message \"Test\"")
    print(SEP.join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
