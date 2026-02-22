#!/usr/bin/env python3
"""
Enterprise audit helper: mask ENV values (4 đầu + 4 cuối), mô tả bảng DB.
Không in lộ secret. Dùng bởi scripts/audit_status.sh trên VPS (/opt/aiplatform).
"""
import re
import sys
from pathlib import Path

# Chỉ liệt kê các key quan trọng; giá trị luôn mask (4 đầu ... 4 cuối)
ENV_KEY_PATTERNS = [
    r"^DATABASE_URL$",
    r"^REDIS_URL$",
    r"^OPENAI_.*",
    r"^FACEBOOK_.*",
    r"^FB_.*",
    r"^N8N_.*",
    r"^WEBHOOK_URL$",
    r"^GDRIVE_.*",
    r"^LOCAL_MEDIA_DIR$",
]


def mask_value(value: str) -> str:
    """
    Mask token: chỉ 4 ký tự đầu và 4 ký tự cuối. Giữa là ...
    Độ dài <= 8 -> **** (không lộ).
    """
    if not value or not value.strip():
        return "(empty)"
    v = value.strip()
    if len(v) <= 8:
        return "****"
    return f"{v[:4]}...{v[-4:]}"


def mask_env_from_lines(lines: list[str]) -> list[str]:
    """Lọc KEY=VALUE theo ENV_KEY_PATTERNS, trả về KEY=mask_value(value)."""
    result = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, rest = line.partition("=")
        key = key.strip()
        # Chỉ lấy value đến hết dòng (cho phép = trong value)
        value = rest.strip().strip('"').strip("'")
        for pat in ENV_KEY_PATTERNS:
            if re.match(pat, key, re.IGNORECASE):
                result.append(f"{key}={mask_value(value)}")
                break
    return result


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: audit_status.py mask_env [path_to_.env]", file=sys.stderr)
        print("       audit_status.py mask_env  (stdin: KEY=VALUE lines)", file=sys.stderr)
        print("       audit_status.py table_descriptions", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "mask_env":
        if len(sys.argv) >= 3:
            env_path = Path(sys.argv[2])
            if not env_path.exists():
                sys.exit(0)
            lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines()
        else:
            lines = sys.stdin.read().splitlines()
        for out in mask_env_from_lines(lines):
            print(out)
        return

    if cmd == "table_descriptions":
        tables = [
            ("tenants", "Tenant / khách hàng (brand, industry)."),
            ("brand_profiles", "Brand profile gắn tenant."),
            ("industry_profiles", "Industry profile."),
            ("generated_plans", "Kế hoạch nội dung sinh bởi AI (plan_json)."),
            ("content_plans", "Plan đã materialize (gắn content_items)."),
            ("content_items", "Bài viết nội dung (title, caption, status, require_media)."),
            ("content_assets", "Ảnh/video từ Google Drive (drive_file_id, local_path, status)."),
            ("publish_logs", "Lịch sử đăng bài (Facebook, status, fb_post_id)."),
            ("approval_events", "Sự kiện approval/reject content."),
            ("post_metrics", "Metrics bài đăng (likes, comments...)."),
            ("kb_items", "Knowledge base items."),
            ("ai_usage_logs", "Log sử dụng AI (token, cost)."),
            ("lead_signals", "B2B lead từ comment/inbox (intent, priority, status)."),
        ]
        for name, desc in tables:
            print(f"- **{name}**: {desc}")
        return

    print("Unknown command.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
