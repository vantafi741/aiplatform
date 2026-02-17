"""
Meta/Facebook post test: dang bai test len Page qua Graph API.
FORMAT_MODE=COMPACT (default): no newline between blocks. FORMAT_MODE=PRETTY: newlines.
Timeout 20s. Never print full token. Chay: python scripts/meta_post_test.py [--message "text"]
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

FORMAT_MODE = os.environ.get("FORMAT_MODE", "COMPACT").strip().upper()
SEP = "" if FORMAT_MODE == "COMPACT" else "\n"
GRAPH_BASE = "https://graph.facebook.com/v24.0"
TIMEOUT = 20

REQUIRED_KEYS = ("FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN")


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Test dang bai len Facebook Page")
    parser.add_argument(
        "--message",
        type=str,
        default="Test post from API",
        help="Noi dung bai dang",
    )
    args = parser.parse_args()

    env = get_env()
    page_id = env["FACEBOOK_PAGE_ID"]
    page_token = env["FACEBOOK_PAGE_ACCESS_TOKEN"]

    url = f"{GRAPH_BASE}/{page_id}/feed"
    payload = {"message": args.message, "access_token": page_token}

    parts = [
        "Sending POST to Page feed...",
        f"  Page ID: {page_id}",
        f"  Message: {args.message}",
    ]

    try:
        r = requests.post(url, data=payload, timeout=TIMEOUT)
        data = r.json() if r.text else {}

        if r.status_code == 200 and "id" in data:
            post_id = data["id"]
            parts.append(f"[OK] Post created. post_id: {post_id}")
            print(SEP.join(parts))
            return 0

        err = data.get("error", {})
        code = err.get("code")
        msg = err.get("message", str(data))
        subcode = err.get("error_subcode")

        parts = [
            f"[FAIL] HTTP {r.status_code}",
            f"  error code:    {code}",
            f"  error message: {msg}",
        ]
        if subcode is not None:
            parts.append(f"  error_subcode: {subcode}")

        if code == 190:
            parts.append("  -> Token expired or invalid. Regenerate Page Access Token.")
        elif code == 10:
            parts.append("  -> Permission denied. Ensure App has pages_manage_posts.")
        elif code == 200:
            parts.append("  -> Missing permission (pages_manage_posts) or Page not linked to App.")
        else:
            parts.append("  -> Missing permission (pages_manage_posts) or Page not linked to App.")

        print(SEP.join(parts))
        return 1

    except requests.RequestException as e:
        print(SEP.join(parts) + SEP + f"[FAIL] Request error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
