"""Thin wrapper cho orchestrator (giu backward compatibility)."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.services.orchestrator_service import run_drive_to_facebook_pipeline


async def run_drive_to_facebook_for_tenant(
    tenant_id: UUID,
    limit: int = 5,
) -> dict[str, Any]:
    """
    Wrapper cũ -> gọi orchestrator mode='scheduled'.
    """
    return await run_drive_to_facebook_pipeline(
        tenant_id=tenant_id,
        options={
            "mode": "scheduled",
            "limit": limit,
            "ingest": False,
            "summarize": False,
            "generate": False,
            "approve": False,
            "publish": True,
            "metrics": True,
        },
    )

