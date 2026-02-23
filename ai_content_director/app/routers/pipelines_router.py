"""Pipelines API: DB-first pipeline runner cho Drive -> Facebook."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, UUID4

from app.services.orchestrator_service import (
    run_drive_to_facebook_pipeline as run_drive_to_facebook_pipeline_orchestrator,
)

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])


class RunPipelineRequest(BaseModel):
    """Body cho POST /api/pipelines/drive_to_facebook/run."""

    tenant_id: UUID4
    options: dict[str, object] | None = Field(
        default=None,
        description="Tuy chon pipeline: mode, limit, ingest, summarize, generate, approve, publish, metrics",
    )


class RunPipelineResponse(BaseModel):
    """Response cho endpoint chạy pipeline."""

    ok: bool
    ingested: int
    summarized: int
    generated: int
    approved: int
    published: int
    metrics_fetched: int
    processed: int
    skipped: int
    errors: list[str]
    now_utc: str


@router.post("/drive_to_facebook/run", response_model=RunPipelineResponse)
async def run_drive_to_facebook_pipeline(
    payload: RunPipelineRequest,
) -> RunPipelineResponse:
    """Run single-source orchestrator pipeline cho tenant."""
    try:
        result = await run_drive_to_facebook_pipeline_orchestrator(
            payload.tenant_id,
            options=payload.options,
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err)) from err

    return RunPipelineResponse(
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
        now_utc=str(result.get("now_utc", "")),
    )

