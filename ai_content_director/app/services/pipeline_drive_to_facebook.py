"""Legacy wrapper cho orchestrator single-source."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.orchestrator_service import run_drive_to_facebook_pipeline as run_orchestrator


@dataclass
class PipelineRunResult:
    """Kết quả nội bộ của một lần chạy pipeline."""

    ingested: int = 0
    summarized: int = 0
    generated: int = 0
    approved: int = 0
    published: int = 0
    metrics_fetched: int = 0
    processed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


async def run_drive_to_facebook_pipeline(
    db: AsyncSession,  # noqa: ARG001 - giu backward compatibility
    *,
    tenant_id: UUID,
) -> PipelineRunResult:
    """
    Legacy API: forward sang orchestrator service.
    """
    out = await run_orchestrator(tenant_id=tenant_id, options={"mode": "full"})
    return PipelineRunResult(
        ingested=int(out.get("ingested", 0)),
        summarized=int(out.get("summarized", 0)),
        generated=int(out.get("generated", 0)),
        approved=int(out.get("approved", 0)),
        published=int(out.get("published", 0)),
        metrics_fetched=int(out.get("metrics_fetched", 0)),
        processed=int(out.get("processed", 0)),
        skipped=int(out.get("skipped", 0)),
        errors=list(out.get("errors", [])),
    )

