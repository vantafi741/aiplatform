"""
Meta/Facebook post test: dang bai test len Page. Deterministic env from repo root.
Posting identity proof: GET /me with final token before POST; print posting_as_id/name, match_status.
If MISMATCH -> exit 4 without posting. Missing required -> exit(2). Post fail -> exit(5). Timeout 20s. Never print full token.
"""
import argparse
from pathlib import Path
import os
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from _meta_common import (
    load_env_deterministic,
    format_env_context,
    get_identity,
    diagnosis_hints_403,
    GRAPH_BASE,
    TIMEOUT,
    EXIT_MISSING_ENV,
    EXIT_PERMISSION_MISSING,
    EXIT_POST_FAIL,
)
MASK_KEYS = {"FACEBOOK_PAGE_ACCESS_TOKEN"}

import requests

POST_REQUIRED_KEYS = ("FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN")

FORMAT_MODE = os.environ.get("FORMAT_MODE", "COMPACT").strip().upper()
SEP = "" if FORMAT_MODE == "COMPACT" else "\n"


def _get_page_token_for_post(page_id: str, token: str) -> str:
    """If token is USER/SYSTEM_USER, get Page token for page_id from /me/accounts. Else return token."""
    try:
        r = requests.get(
            f"{GRAPH_BASE}/me/accounts",
            params={"fields": "id,access_token", "access_token": token},
            timeout=TIMEOUT,
        )
        if not r.ok:
            return token
        data = r.json()
        for p in data.get("data") or []:
            if str(p.get("id")) == str(page_id):
                return p.get("access_token", token)
    except requests.RequestException:
        pass
    return token


def get_env() -> dict:
    cwd = Path.cwd()
    repo_root, env_path, env_dict, source_map = load_env_deterministic(
        SCRIPT_DIR, POST_REQUIRED_KEYS, ()
    )
    missing = [k for k in POST_REQUIRED_KEYS if k not in env_dict or not env_dict[k]]
    if missing:
        lines = [
            "[ERROR] Thieu bien moi truong: " + ", ".join(missing),
            "Chay tu repo root de load .env:  cd " + str(repo_root),
            "Chay: python scripts/meta_env_doctor.py de xem huong dan.",
        ]
        print(SEP.join(lines) if SEP else "".join(lines))
        sys.exit(EXIT_MISSING_ENV)
    return env_dict


def main() -> int:
    parser = argparse.ArgumentParser(description="Test dang bai len Facebook Page")
    parser.add_argument("--message", type=str, default="Test post from API", help="Noi dung bai dang")
    args = parser.parse_args()

    env = get_env()
    page_id = env["FACEBOOK_PAGE_ID"]
    page_token = env["FACEBOOK_PAGE_ACCESS_TOKEN"]
    page_token = _get_page_token_for_post(page_id, page_token)

    cwd = Path.cwd()
    repo_root, env_path, _, source_map = load_env_deterministic(SCRIPT_DIR, POST_REQUIRED_KEYS, ())
    context_lines = format_env_context(
        cwd, repo_root, env_path, source_map, env,
        POST_REQUIRED_KEYS, (), MASK_KEYS
    )

    parts = ["Env context:"]
    parts.extend(context_lines)
    parts.append("-" * 60)

    identity = get_identity(page_token)
    posting_as_id = identity.get("id")
    posting_as_name = identity.get("name", "")
    if "error" in identity:
        parts.append("Posting identity proof: [FAIL] /me: " + str(identity.get("error")))
        parts.append("  -> Cannot resolve token identity; check token and permissions.")
        print(SEP.join(parts))
        sys.exit(EXIT_PERMISSION_MISSING)

    expected_page_id = page_id
    match = str(posting_as_id) == str(expected_page_id)
    match_status = "MATCH" if match else "MISMATCH"
    posting_token_type = "PAGE" if match else "unknown (binding mismatch)"

    parts.append("Posting identity proof:")
    parts.append(f"  posting_token_type: {posting_token_type}")
    parts.append(f"  posting_as_id:       {posting_as_id}")
    parts.append(f"  posting_as_name:    {posting_as_name}")
    parts.append(f"  expected_page_id:   {expected_page_id}")
    parts.append(f"  match_status:       {match_status}")

    if not match:
        parts.append("")
        parts.append("Token is bound to a different Page than FACEBOOK_PAGE_ID.")
        parts.append("Fix: update FACEBOOK_PAGE_ID in .env to match the Page this token is for, or fetch the correct Page token for FACEBOOK_PAGE_ID (e.g. via meta_verify /me/accounts).")
        parts.extend(diagnosis_hints_403(page_id_env=expected_page_id, page_id_token=str(posting_as_id)))
        print(SEP.join(parts))
        sys.exit(EXIT_PERMISSION_MISSING)

    parts.append("-" * 60)
    parts.append("Sending POST to Page feed...")
    parts.append(f"  Page ID: {page_id}")
    parts.append(f"  Message: {args.message}")

    url = f"{GRAPH_BASE}/{page_id}/feed"
    payload = {"message": args.message, "access_token": page_token}

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

        parts.append(f"[FAIL] HTTP {r.status_code}")
        parts.append(f"  error code:    {code}")
        parts.append(f"  error message: {msg}")
        if subcode is not None:
            parts.append(f"  error_subcode: {subcode}")

        if code == 190:
            parts.append("  -> Token expired or invalid. Regenerate Page Access Token.")
        elif code == 10:
            parts.append("  -> Permission denied. Ensure App has pages_manage_posts.")
        elif code == 200:
            parts.append("  -> Missing permission (pages_manage_posts) or Page not linked to App.")
            parts.extend(diagnosis_hints_403(page_id_env=page_id))
        else:
            parts.append("  -> Missing permission (pages_manage_posts) or Page not linked to App.")
            parts.extend(diagnosis_hints_403(page_id_env=page_id))

        print(SEP.join(parts))
        sys.exit(EXIT_POST_FAIL)

    except requests.RequestException as e:
        parts.append(f"[FAIL] Request error: {e}")
        print(SEP.join(parts))
        sys.exit(EXIT_POST_FAIL)


if __name__ == "__main__":
    sys.exit(main())
