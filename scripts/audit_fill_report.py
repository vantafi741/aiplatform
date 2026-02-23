#!/usr/bin/env python3
"""
Fill docs/RUNTIME_AUDIT_REPORT.md from raw runtime audit output.

This script is intentionally read-only regarding business logic and never prints secret values.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


@dataclass
class RawAudit:
    meta: Dict[str, str]
    sections: Dict[str, str]


def sanitize_text(text: str) -> str:
    """Sanitize mojibake/console artifacts to readable ASCII-safe text."""
    if not text:
        return text
    cleaned = text
    # Common mojibake seen on Windows terminals.
    cleaned = cleaned.replace("ΓÇª", "...")
    cleaned = cleaned.replace("â€¦", "...")
    # Remove ANSI color/control sequences.
    cleaned = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", cleaned)
    # Replace non-ASCII chars with ASCII placeholder for report readability.
    cleaned = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", "...", cleaned)
    # Collapse repeated placeholders.
    cleaned = re.sub(r"(?:\.\.\.){2,}", "...", cleaned)
    return cleaned


def parse_raw(raw_text: str) -> RawAudit:
    """Parse raw audit text with section markers."""
    meta: Dict[str, str] = {}
    sections: Dict[str, List[str]] = {}
    current_key: str | None = None

    for line in sanitize_text(raw_text).splitlines():
        if line.startswith("###BEGIN:"):
            current_key = line.split("###BEGIN:", 1)[1].strip()
            sections[current_key] = []
            continue

        if line.startswith("###END:"):
            current_key = None
            continue

        if current_key is not None:
            sections[current_key].append(line)
            continue

        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            meta[key.strip()] = value.strip()

    sections_joined = {k: "\n".join(v).strip() for k, v in sections.items()}
    return RawAudit(meta=meta, sections=sections_joined)


def code_block(content: str) -> str:
    """Render content in markdown code block with fallback."""
    body = sanitize_text(content.strip()) if content and content.strip() else "n/a"
    return f"```text\n{body}\n```"


def build_report(raw: RawAudit, repo_root: str, api_base_url: str) -> str:
    """Build markdown report text from parsed raw sections."""
    mode = raw.meta.get("mode", "VPS").upper()
    generated_at = raw.meta.get(
        "generated_at", datetime.now(tz=timezone.utc).isoformat()
    )

    rows = [
        "# Runtime Audit Report (VPS)",
        f"mode={mode}",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Repo root: `{repo_root}`",
        f"- API base URL: `{api_base_url}`",
        "",
        "## 1) Git Branch + Last Commit",
        code_block(raw.sections.get("GIT", "")),
        "",
        "## 2) Docker Compose PS (Health)",
        code_block(raw.sections.get("DOCKER_PS", "")),
        "",
        "## 3) API Logs (tail 200)",
        code_block(raw.sections.get("API_LOGS", "")),
        "",
        "## 4) API Health Check",
        code_block(raw.sections.get("HEALTHZ", "")),
        "",
        "## 5) OpenAPI Path Count",
        code_block(raw.sections.get("OPENAPI", "")),
        "",
        "## 6) PostgreSQL Tables",
        code_block(raw.sections.get("DB_TABLES", "")),
        "",
        "## 7) PostgreSQL Row Counts (Top 15)",
        code_block(raw.sections.get("DB_ROW_COUNTS", "")),
        "",
        "## 8) Alembic Current",
        code_block(raw.sections.get("ALEMBIC_CURRENT", "")),
        "",
        "## 9) Alembic History (Last 10)",
        code_block(raw.sections.get("ALEMBIC_HISTORY", "")),
        "",
        "## 10) Important ENV Variables (Length Only)",
        "> Security note: values are hidden, only lengths are shown.",
        code_block(raw.sections.get("ENV_LENGTHS", "")),
        "",
        "---",
        "Audit checklist:",
        "- [ ] Report generated/refreshed successfully.",
        "- [ ] No secret values exposed in report.",
    ]
    return "\n".join(rows).strip() + "\n"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Fill runtime audit markdown report.")
    parser.add_argument("--raw", required=True, help="Path to raw audit text file.")
    parser.add_argument("--out", required=True, help="Output markdown report path.")
    parser.add_argument("--repo-root", required=True, help="Repository root path.")
    parser.add_argument("--api-base-url", required=True, help="API base URL.")
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = parse_args()
    raw_path = Path(args.raw)
    out_path = Path(args.out)

    raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
    parsed = parse_raw(raw_text)
    report = build_report(
        raw=parsed,
        repo_root=args.repo_root,
        api_base_url=args.api_base_url,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
