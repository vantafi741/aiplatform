"""
Meta/Facebook post test: đăng một bài test lên Page qua Graph API.

POST /{FACEBOOK_PAGE_ID}/feed với message (mặc định hoặc --message).
In post_id nếu thành công; nếu lỗi in error code + message (200/190/10).
Chạy: python scripts/meta_post_test.py [--message "Nội dung"]
"""
import argparse
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

REQUIRED_KEYS = ("FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN")


def mask_secret(value: str, visible: int = 6) -> str:
    """Mask token: 6 chars + ... + 6 chars. Never print full value."""
    if not value or not value.strip():
        return "(empty)"
    s = value.strip()
    if len(s) <= visible * 2:
        return "***"
    return f"{s[:visible]}...{s[-visible:]}"


def get_env() -> dict:
    """Lấy ENV; thiếu thì báo lỗi."""
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


def main() -> int:
    """Đăng bài test lên Page."""
    parser = argparse.ArgumentParser(description="Test đăng bài lên Facebook Page")
    parser.add_argument(
        "--message",
        type=str,
        default="Test đăng bài từ server (meta_post_test.py)",
        help="Nội dung bài đăng",
    )
    args = parser.parse_args()

    env = get_env()
    page_id = env["FACEBOOK_PAGE_ID"]
    page_token = env["FACEBOOK_PAGE_ACCESS_TOKEN"]

    url = f"{GRAPH_BASE}/{page_id}/feed"
    payload = {"message": args.message, "access_token": page_token}

    print("Sending POST to Page feed...")
    print(f"  Page ID: {page_id}")
    print(f"  Message: {args.message}")

    try:
        r = requests.post(url, data=payload, timeout=15)
        data = r.json() if r.text else {}

        if r.status_code == 200 and "id" in data:
            post_id = data["id"]
            print(f"[OK] Post created. post_id: {post_id}")
            return 0

        err = data.get("error", {})
        code = err.get("code")
        msg = err.get("message", str(data))
        subcode = err.get("error_subcode")

        print(f"[FAIL] HTTP {r.status_code}")
        print(f"  error code:    {code}")
        print(f"  error message: {msg}")
        if subcode is not None:
            print(f"  error_subcode: {subcode}")

        if code == 190:
            print("  -> Token expired or invalid. Regenerate Page Access Token.")
        elif code == 10:
            print("  -> Permission denied. Ensure App has pages_manage_posts.")
        elif code == 200:
            print("  -> Missing permission (pages_manage_posts) or Page not linked to App.")

        return 1

    except requests.RequestException as e:
        print(f"\n[FAIL] Request error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
