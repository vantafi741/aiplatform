"""
Meta/Facebook ENV doctor: check Meta env vars and print where to get each key.
Never logs full tokens. mask_secret: 6+...+6 or if len<13 then 2+...+2.
FORMAT_MODE=COMPACT (default): no newline between blocks. FORMAT_MODE=PRETTY: newlines.
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

FORMAT_MODE = os.environ.get("FORMAT_MODE", "COMPACT").strip().upper()
SEP = "" if FORMAT_MODE == "COMPACT" else "\n"

REQUIRED_KEYS = (
    "META_APP_ID",
    "META_APP_SECRET",
    "FACEBOOK_PAGE_ID",
    "FACEBOOK_PAGE_ACCESS_TOKEN",
)
OPTIONAL_KEYS = (
    "META_BUSINESS_ID",
    "META_SYSTEM_USER_ID",
    "WEBHOOK_VERIFY_TOKEN",
    "WEBHOOK_SECRET",
)

GUIDANCE = {
    "META_APP_ID": "Meta App dashboard -> Settings -> Basic -> App ID",
    "META_APP_SECRET": "Meta App dashboard -> Settings -> Basic -> App Secret (Show)",
    "META_BUSINESS_ID": "Business Settings -> Business Manager ID (if using BM)",
    "META_SYSTEM_USER_ID": "Business Settings -> Users -> System Users -> ID (long-lived token)",
    "FACEBOOK_PAGE_ID": "Page About -> Page ID; or /me/accounts in Graph Explorer",
    "FACEBOOK_PAGE_ACCESS_TOKEN": "Graph Explorer -> Get Token -> Get Page Access Token; or System User token",
    "WEBHOOK_VERIFY_TOKEN": "Custom string for Meta webhook verification",
    "WEBHOOK_SECRET": "Webhook app secret for payload signing",
}


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


def main() -> int:
    missing = []
    rows = []

    for key in REQUIRED_KEYS:
        val = os.environ.get(key)
        if not val or not str(val).strip():
            missing.append(key)
            rows.append((key, "(empty)", "SKIP"))
        else:
            if "SECRET" in key or "TOKEN" in key or "ACCESS" in key:
                rows.append((key, mask_secret(val), "OK"))
            else:
                rows.append((key, val.strip(), "OK"))

    for key in OPTIONAL_KEYS:
        val = os.environ.get(key)
        if not val or not str(val).strip():
            rows.append((key, "(empty)", "SKIP"))
        else:
            if "SECRET" in key or "TOKEN" in key:
                rows.append((key, mask_secret(val), "OK"))
            else:
                rows.append((key, val.strip(), "OK"))

    parts = [
        "=" * 60,
        "Meta/Facebook ENV Doctor",
        "=" * 60,
        f"Reading .env from: {REPO_ROOT / '.env'}",
        "Env status:",
        "-" * 60,
    ]
    for key, display, tag in rows:
        parts.append(f"  {key}: {display}  [{tag}]")
    parts.append("-" * 60)

    if missing:
        parts.append("")
        parts.append("Required keys missing: " + ", ".join(missing))
        parts.append("Where to get each key:")
        for key in missing:
            parts.append(f"  * {key}")
            parts.append(f"    -> {GUIDANCE.get(key, 'See docs/META_SETUP.md')}")
        parts.append("")
        parts.append("After filling .env run: python scripts/meta_verify.py")
        print(SEP.join(parts))
        return 1

    parts.append("Next: python scripts/meta_verify.py")
    print(SEP.join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
