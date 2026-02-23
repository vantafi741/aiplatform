"""Scheduler status API."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.db import get_db
from app.logging_config import get_logger
from app.models import ContentItem
from app.schemas.scheduler import (
    SchedulerRunPublishTickRequest,
    SchedulerRunPublishTickResponse,
    SchedulerStatusResponse,
)
from app.services.drive_to_facebook_pipeline_service import (
    run_drive_to_facebook_for_tenant,
)
from app.services.scheduler_service import (
    get_scheduler_status,
    get_scheduler_status_with_pending,
)
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
logger = get_logger(__name__)


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status_endpoint(
    db: AsyncSession = Depends(get_db),
) -> SchedulerStatusResponse:
    """Trạng thái worker scheduler: enabled, interval, last_tick_at, pending_count."""
    status = await get_scheduler_status_with_pending(db)
    return SchedulerStatusResponse(
        enabled=status["enabled"],
        interval_seconds=status["interval_seconds"],
        last_tick_at=status["last_tick_at"],
        pending_count=status["pending_count"],
    )


@router.post("/run_publish_tick", response_model=SchedulerRunPublishTickResponse)
async def post_run_publish_tick(
    payload: SchedulerRunPublishTickRequest,
    db: AsyncSession = Depends(get_db),
) -> SchedulerRunPublishTickResponse:
    """Manual trigger publish tick: gọi nội bộ pipeline theo tenant."""
    now_utc = datetime.now(timezone.utc)
    scheduler_status = get_scheduler_status()
    if scheduler_status.get("enabled"):
        logger.error(
            "scheduler.policy_conflict",
            message=(
                "Internal scheduler is enabled while /api/scheduler/run_publish_tick "
                "is being triggered (likely from n8n). Disable internal scheduler "
                "to avoid double-run."
            ),
        )
    errors: list[str] = []
    processed = 0
    skipped = 0

    tenant_ids: list[str] = []
    if payload.tenant_id:
        tenant_ids = [payload.tenant_id]
    else:
        q = (
            select(ContentItem.tenant_id)
            .where(
                ContentItem.status == "approved",
                ContentItem.schedule_status == "scheduled",
                ContentItem.scheduled_at.is_not(None),
                ContentItem.scheduled_at <= now_utc,
            )
            .distinct()
            .limit(payload.batch_size)
        )
        r = await db.execute(q)
        tenant_ids = [str(row[0]) for row in r.all()]
        if not tenant_ids:
            logger.info(
                "scheduler.run_publish_tick.no_eligible_tenant",
                batch_size=payload.batch_size,
            )

    logger.info(
        "scheduler.run_publish_tick.start",
        tenant_id=payload.tenant_id,
        tenant_count=len(tenant_ids),
        batch_size=payload.batch_size,
    )

    for tenant_id in tenant_ids:
        try:
            tenant_uuid = UUID(tenant_id)
            result = await run_drive_to_facebook_for_tenant(
                tenant_id=tenant_uuid,
                limit=payload.batch_size,
            )
            processed += int(result.get("processed", 0))
            skipped += int(result.get("skipped", 0))
            errors.extend(list(result.get("errors", [])))
        except Exception as err:
            skipped += 1
            errors.append(f"{tenant_id}: {err}")

    logger.info(
        "scheduler.run_publish_tick.done",
        tenant_id=payload.tenant_id,
        processed=processed,
        skipped=skipped,
        tenant_count=len(tenant_ids),
    )

    return SchedulerRunPublishTickResponse(
        ok=True,
        processed=processed,
        skipped=skipped,
        errors=errors,
        now_utc=now_utc.isoformat(),
    )
