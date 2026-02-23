"""Legacy API wrapper -> orchestrator_service (single source of truth)."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.orchestrator_service import run_drive_to_facebook_pipeline

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


class DriveToFacebookRunRequest(BaseModel):
    """Body cho endpoint run pipeline."""

    tenant_id: UUID = Field(..., description="Tenant UUID")


class DriveToFacebookRunResponse(BaseModel):
    """Response chuẩn cho pipeline run."""

    ok: bool = True
    ingested: int = 0
    summarized: int = 0
    generated: int = 0
    approved: int = 0
    published: int = 0
    metrics_fetched: int = 0
    processed: int = 0
    skipped: int = 0
    errors: List[str] = Field(default_factory=list)


@router.post("/drive_to_facebook/run", response_model=DriveToFacebookRunResponse)
async def run_drive_to_facebook(
    payload: DriveToFacebookRunRequest,
) -> DriveToFacebookRunResponse:
    """Legacy endpoint: forward sang orchestrator để tránh duplicate logic."""
    try:
        result = await run_drive_to_facebook_pipeline(
            tenant_id=payload.tenant_id,
            options={"mode": "full"},
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err)) from err

    return DriveToFacebookRunResponse(
        ok=bool(result.get("ok", True)),
        ingested=int(result.get("ingested", 0)),
        summarized=int(result.get("summarized", 0)),
        generated=int(result.get("generated", 0)),
        approved=int(result.get("approved", 0)),
        published=int(result.get("published", 0)),
        metrics_fetched=int(result.get("metrics_fetched", 0)),
        processed=int(result.get("processed", 0)),
        skipped=int(result.get("skipped", 0)),
        errors=list(result.get("errors", [])),
    )

