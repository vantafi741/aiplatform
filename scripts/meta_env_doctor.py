"""
Meta/Facebook ENV doctor: check Meta env vars and print where to get each key.
Never logs full tokens (mask first/last 6 chars). Run: python scripts/meta_env_doctor.py
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
OPTIONAL_KEYS = ("META_BUSINESS_ID", "META_SYSTEM_USER_ID")

GUIDANCE = {
    "META_APP_ID": "Meta App dashboard -> Settings -> Basic -> App ID",
    "META_APP_SECRET": "Meta App dashboard -> Settings -> Basic -> App Secret (Show)",
    "META_BUSINESS_ID": "Business Settings -> Business Manager ID (if using BM)",
    "META_SYSTEM_USER_ID": "Business Settings -> Users -> System Users -> ID (long-lived token)",
    "FACEBOOK_PAGE_ID": "Page About -> Page ID; or /me/accounts in Graph Explorer",
    "FACEBOOK_PAGE_ACCESS_TOKEN": "Graph Explorer -> Get Token -> Get Page Access Token; or System User token",
}


def mask_token(value: str, visible: int = 6) -> str:
    if not value or not value.strip():
        return "(empty)"
    s = value.strip()
    if len(s) <= visible * 2:
        return "***"
    return f"{s[:visible]}...{s[-visible:]}"


def main() -> int:
    print("=" * 60)
    print("Meta/Facebook ENV Doctor")
    print("=" * 60)
    print(f"Reading .env from: {REPO_ROOT / '.env'}")
    print()

    missing = []
    present = []

    for key in REQUIRED_KEYS:
        val = os.environ.get(key)
        if not val or not str(val).strip():
            missing.append(key)
            present.append((key, None))
        else:
            if "SECRET" in key or "TOKEN" in key or "ACCESS" in key:
                present.append((key, mask_token(val)))
            else:
                present.append((key, val))

    for key in OPTIONAL_KEYS:
        val = os.environ.get(key)
        if not val or not str(val).strip():
            present.append((key, "(not set)"))
        else:
            if "SECRET" in key or "TOKEN" in key:
                present.append((key, mask_token(val)))
            else:
                present.append((key, val))

    print("Env status:")
    print("-" * 60)
    for key, val in present:
        status = "OK" if val and val not in ("(empty)", "(not set)") else "MISSING"
        display = val or "(empty)"
        print(f"  {key}: {display}  [{status}]")
    print("-" * 60)

    if missing:
        print("\nRequired keys missing:", ", ".join(missing))
        print("\nWhere to get each key:")
        for key in missing:
            print(f"  * {key}")
            print(f"    -> {GUIDANCE.get(key, 'See docs/META_SETUP.md')}")
        print("\nAfter filling .env run: python scripts/meta_verify.py")
        return 1

    print("\nReference (where to get keys):")
    for key in REQUIRED_KEYS + OPTIONAL_KEYS:
        print(f"  * {key}: {GUIDANCE.get(key, '-')}")
    print("\nNext: python scripts/meta_verify.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
