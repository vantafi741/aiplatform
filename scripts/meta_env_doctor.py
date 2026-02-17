"""
Meta/Facebook ENV doctor: check Meta env vars, deterministic env from repo root.
Prints cwd, repo_root, env_path, and source (env vs .env) per var.
Missing required -> exit(2) and suggest cd to repo root.
FORMAT_MODE=COMPACT | PRETTY. Never logs full tokens.
"""
from pathlib import Path
import os
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from _meta_common import (
    load_env_deterministic,
    mask_secret,
    format_env_context,
    REQUIRED_META_KEYS,
    OPTIONAL_META_KEYS,
    EXIT_MISSING_ENV,
)
MASK_KEYS = {k for k in REQUIRED_META_KEYS + OPTIONAL_META_KEYS if "SECRET" in k or "TOKEN" in k or "ACCESS" in k}

FORMAT_MODE = os.environ.get("FORMAT_MODE", "COMPACT").strip().upper()
SEP = "" if FORMAT_MODE == "COMPACT" else "\n"

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


def main() -> int:
    cwd = Path.cwd()
    repo_root, env_path, env_dict, source_map = load_env_deterministic(
        SCRIPT_DIR, REQUIRED_META_KEYS, OPTIONAL_META_KEYS
    )

    missing = [k for k in REQUIRED_META_KEYS if k not in env_dict or not env_dict[k]]
    context_lines = format_env_context(
        cwd, repo_root, env_path, source_map, env_dict,
        REQUIRED_META_KEYS, OPTIONAL_META_KEYS, MASK_KEYS
    )

    parts = [
        "=" * 60,
        "Meta/Facebook ENV Doctor",
        "=" * 60,
        "Env loading (deterministic from repo root):",
    ]
    parts.extend(context_lines)
    parts.append("-" * 60)
    parts.append("Env status:")

    for k in REQUIRED_META_KEYS + OPTIONAL_META_KEYS:
        val = env_dict.get(k)
        if not val:
            tag = "SKIP" if k in OPTIONAL_META_KEYS else "MISSING"
            display = "(empty)"
        else:
            tag = "OK"
            display = mask_secret(val) if k in MASK_KEYS else val
        parts.append(f"  {k}: {display}  [{tag}]")
    parts.append("-" * 60)

    if missing:
        parts.append("")
        parts.append("Required keys missing: " + ", ".join(missing))
        parts.append("Where to get each key:")
        for key in missing:
            parts.append(f"  * {key}")
            parts.append(f"    -> {GUIDANCE.get(key, 'See docs/META_SETUP.md')}")
        parts.append("")
        parts.append("Hint: run from repo root so .env is found:  cd " + str(repo_root))
        parts.append("Then: python scripts/meta_env_doctor.py")
        print(SEP.join(parts))
        sys.exit(EXIT_MISSING_ENV)

    parts.append("Next: python scripts/meta_verify.py")
    print(SEP.join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
