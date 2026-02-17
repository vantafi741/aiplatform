"""
Env override fix helper: detect process env overriding .env and print shell commands to clear.
Run from repo root. Exit 0 if no overrides, 1 if overrides detected (so CI/users can notice).
Never prints full tokens/secrets; uses mask_secret for values shown.
"""
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from _meta_common import (
    load_env_deterministic,
    mask_secret,
    REQUIRED_META_KEYS,
    OPTIONAL_META_KEYS,
)

KEYS_TO_CHECK = (
    "META_APP_ID",
    "META_APP_SECRET",
    "FACEBOOK_PAGE_ID",
    "FACEBOOK_PAGE_ACCESS_TOKEN",
    "META_BUSINESS_ID",
    "META_SYSTEM_USER_ID",
)
MASK_KEYS = {k for k in KEYS_TO_CHECK if "SECRET" in k or "TOKEN" in k or "ACCESS" in k}


def main() -> int:
    repo_root, env_path, env_dict, source_map = load_env_deterministic(
        SCRIPT_DIR, REQUIRED_META_KEYS, OPTIONAL_META_KEYS
    )
    overrides = [k for k in KEYS_TO_CHECK if source_map.get(k) == "env (overrides .env)"]

    print("Meta env override check (repo_root=%s)" % repo_root)
    print("-" * 60)

    if not overrides:
        print("No overrides detected. Process env is not overriding .env for Meta keys.")
        print("Recommended: python scripts/meta_env_doctor.py")
        return 0

    print("Keys currently overriding .env (set in process env before load_dotenv):")
    for k in overrides:
        val = env_dict.get(k, "")
        display = mask_secret(val) if k in MASK_KEYS else (val[:20] + "..." if val and len(val) > 20 else val)
        print("  %s: %s  [source: env (overrides .env)]" % (k, display or "(empty)"))
    print("-" * 60)
    print("Run the following in your current shell to clear overrides, then rerun scripts.")
    print("")
    print("PowerShell:")
    for k in overrides:
        print("  Remove-Item Env:%s -ErrorAction SilentlyContinue" % k)
    print("")
    print("CMD:")
    for k in overrides:
        print("  set %s=" % k)
    print("")
    print("Git Bash / Bash:")
    for k in overrides:
        print("  unset %s" % k)
    print("-" * 60)
    print("Recommended clean run (after clearing overrides):")
    print("  python scripts/meta_env_doctor.py")
    print("  python scripts/meta_verify.py")
    print("  python scripts/meta_post_test.py --message \"Test\"")
    return 1


if __name__ == "__main__":
    sys.exit(main())
