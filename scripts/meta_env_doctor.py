"""
Meta/Facebook ENV doctor: check Meta env vars and print where to get each key.
Never logs full tokens (mask 6 chars + ... + 6 chars). Run: python scripts/meta_env_doctor.py
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


def mask_secret(value: str, visible: int = 6) -> str:
    """Mask secret/token: 6 chars + ... + 6 chars. Never print full value."""
    if not value or not value.strip():
        return "(empty)"
    s = value.strip()
    if len(s) <= visible * 2:
        return "***"
    return f"{s[:visible]}...{s[-visible:]}"


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

    print("=" * 60)
    print("Meta/Facebook ENV Doctor")
    print("=" * 60)
    print(f"Reading .env from: {REPO_ROOT / '.env'}")
    print("Env status:")
    print("-" * 60)
    for key, display, tag in rows:
        print(f"  {key}: {display}  [{tag}]")
    print("-" * 60)

    if missing:
        print("\nRequired keys missing:", ", ".join(missing))
        print("\nWhere to get each key:")
        for key in missing:
            print(f"  * {key}")
            print(f"    -> {GUIDANCE.get(key, 'See docs/META_SETUP.md')}")
        print("\nAfter filling .env run: python scripts/meta_verify.py")
        return 1

    print("\nNext: python scripts/meta_verify.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
