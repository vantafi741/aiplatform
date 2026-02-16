"""
Meta/Facebook token verification: kiem tra token hop le, lay Page info, debug token.

Doc ENV: META_APP_ID, META_APP_SECRET, FACEBOOK_PAGE_ID, FACEBOOK_PAGE_ACCESS_TOKEN
(optional: META_BUSINESS_ID, META_SYSTEM_USER_ID).
Goi Graph API: /me, /{PAGE_ID}, /debug_token. In bang token_valid, scopes, page info.
Khong in full token ra console (mask).
Chay: python scripts/meta_verify.py
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

GRAPH_BASE = "https://graph.facebook.com/v24.0"

REQUIRED_KEYS = (
    "META_APP_ID",
    "META_APP_SECRET",
    "FACEBOOK_PAGE_ID",
    "FACEBOOK_PAGE_ACCESS_TOKEN",
)


def mask_token(value: str, visible: int = 6) -> str:
    """Che token khi in log."""
    if not value or not value.strip():
        return "(trong)"
    s = value.strip()
    if len(s) <= visible * 2:
        return "***"
    return f"{s[:visible]}...{s[-visible:]}"


def get_env() -> dict:
    """Lay ENV can thiet; thieu thi bao loi ro key."""
    env = {}
    missing = []
    for key in REQUIRED_KEYS:
        val = os.environ.get(key)
        if not val or not str(val).strip():
            missing.append(key)
        else:
            env[key] = val.strip()
    if missing:
        print(f"[ERROR] Thieu bien moi truong: {', '.join(missing)}")
        print("Chay: python scripts/meta_env_doctor.py de xem huong dan.")
        sys.exit(1)
    return env


def debug_token(app_id: str, app_secret: str, page_token: str) -> dict:
    """Goi Graph API debug_token."""
    url = f"{GRAPH_BASE}/debug_token"
    params = {
        "input_token": page_token,
        "access_token": f"{app_id}|{app_secret}",
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("data", {})
    except requests.RequestException as e:
        return {"error": str(e), "is_valid": False}


def main() -> int:
    """Verify token va in bang ket qua."""
    env = get_env()
    app_id = env["META_APP_ID"]
    app_secret = env["META_APP_SECRET"]
    page_id = env["FACEBOOK_PAGE_ID"]
    page_token = env["FACEBOOK_PAGE_ACCESS_TOKEN"]

    print("=" * 60)
    print("Meta/Facebook Token Verification")
    print("=" * 60)
    print(f"Token (masked): {mask_token(page_token)}")
    print()

    me_url = f"{GRAPH_BASE}/me"
    me_params = {"fields": "id,name", "access_token": page_token}
    try:
        me_resp = requests.get(me_url, params=me_params, timeout=15)
        me_data = me_resp.json() if me_resp.ok else {}
        if "error" in me_data:
            print("[FAIL] /me:", me_data["error"].get("message", me_data["error"]))
            me_id = me_name = None
        else:
            me_id = me_data.get("id")
            me_name = me_data.get("name", "")
            print(f"[OK] /me: id={me_id}, name={me_name}")
    except requests.RequestException as e:
        print(f"[FAIL] /me: {e}")
        me_id = me_name = None
        me_data = {}

    page_url = f"{GRAPH_BASE}/{page_id}"
    page_params = {"fields": "id,name,link,fan_count", "access_token": page_token}
    try:
        page_resp = requests.get(page_url, params=page_params, timeout=15)
        page_data = page_resp.json() if page_resp.ok else {}
        if "error" in page_data:
            print(f"[FAIL] /{page_id}:", page_data["error"].get("message", page_data["error"]))
            page_info = None
        else:
            page_info = page_data
            print(f"[OK] Page: id={page_info.get('id')}, name={page_info.get('name')}, "
                  f"link={page_info.get('link')}, fan_count={page_info.get('fan_count')}")
    except requests.RequestException as e:
        print(f"[FAIL] Page request: {e}")
        page_info = None

    debug = debug_token(app_id, app_secret, page_token)
    valid = debug.get("is_valid", False)
    app_id_debug = debug.get("app_id", "")
    user_id = debug.get("user_id", "")
    expires_at = debug.get("expires_at", 0)
    scopes = debug.get("scopes", [])
    if isinstance(expires_at, int) and expires_at > 0:
        from datetime import datetime
        exp_str = datetime.utcfromtimestamp(expires_at).isoformat() + "Z"
    else:
        exp_str = "never" if expires_at == 0 else str(expires_at)

    print()
    print("Ket qua debug_token:")
    print("-" * 60)
    print(f"  token_valid:  {valid}")
    print(f"  app_id:       {app_id_debug}")
    print(f"  user_id:      {user_id}")
    print(f"  expires_at:   {exp_str}")
    print(f"  scopes:       {', '.join(scopes) if scopes else '(empty)'}")
    print("-" * 60)

    if not valid:
        err = debug.get("error") or debug.get("message")
        print("\n[Token khong hop le]")
        if err:
            print(f"  Chi tiet: {err}")
        print("  Huong dan:")
        print("  - Tao lai Page Access Token: Graph Explorer -> Get Token -> Get Page Access Token")
        print("  - Hoac dung System User token (Business Settings -> System Users -> Generate Token)")
        print("  - Can quyen: pages_manage_posts, pages_read_engagement")
        print("  - App che do Development: chi admin/tester thay bai dang")
        return 1

    print("\n[OK] Token hop le. Co the chay: python scripts/meta_post_test.py --message \"Test\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
