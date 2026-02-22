"""Pipelines API: DB-first pipeline runner cho Drive -> Facebook."""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, UUID4
from sqlalchemy import select

from app.db import async_session_factory
from app.models import ContentItem
from app.services.facebook_publish_service import publish_post

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])


class RunPipelineRequest(BaseModel):
    """Body cho POST /api/pipelines/drive_to_facebook/run."""

    tenant_id: UUID4


class RunPipelineResponse(BaseModel):
    """Response cho endpoint chạy pipeline."""

    ok: bool
    processed: int
    skipped: int
    errors: list[str]
    now_utc: str


@router.post("/drive_to_facebook/run", response_model=RunPipelineResponse)
async def run_drive_to_facebook_pipeline(
    payload: RunPipelineRequest,
) -> RunPipelineResponse:
    """Run DB-first pipeline cho tối đa 5 content item đủ điều kiện publish."""
    now_utc = datetime.now(timezone.utc)
    processed = 0
    skipped = 0
    errors: list[str] = []

    async with async_session_factory() as db:
        try:
            q = (
                select(ContentItem)
                .where(
                    ContentItem.tenant_id == payload.tenant_id,
                    ContentItem.status == "approved",
                    ContentItem.schedule_status == "scheduled",
                    ContentItem.scheduled_at.is_not(None),
                    ContentItem.scheduled_at <= now_utc,
                )
                .order_by(ContentItem.scheduled_at.asc(), ContentItem.created_at.asc())
                .limit(5)
            )
            result = await db.execute(q)
            items = list(result.scalars().all())

            for item in items:
                item.publish_attempts = (item.publish_attempts or 0) + 1
                try:
                    publish_result = await publish_post(
                        db,
                        tenant_id=payload.tenant_id,
                        content_id=item.id,
                        actor="SYSTEM",
                        use_latest_asset=True,
                    )
                    log = publish_result[0]
                    error_message = publish_result[1]
                    _ = log  # giữ biến log để phản ánh contract nội bộ

                    if error_message:
                        item.last_publish_error = error_message
                        skipped += 1
                        errors.append(f"{item.id}: {error_message}")
                    else:
                        item.last_publish_at = datetime.now(timezone.utc)
                        item.schedule_status = "published"
                        item.last_publish_error = None
                        processed += 1
                except Exception as err:
                    item.last_publish_error = str(err)
                    skipped += 1
                    errors.append(f"{item.id}: {err}")

                db.add(item)

            await db.commit()
        except Exception as err:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"pipeline_failed: {err}",
            ) from err

    return RunPipelineResponse(
        ok=True,
        processed=processed,
        skipped=skipped,
        errors=errors,
        now_utc=now_utc.isoformat(),
    )

