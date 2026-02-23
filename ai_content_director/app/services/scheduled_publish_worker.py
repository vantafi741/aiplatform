"""Worker publish scheduled (thin wrapper gọi orchestrator)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db import async_session_factory
from app.logging_config import get_logger
from app.models import ContentItem
from app.services.orchestrator_service import run_drive_to_facebook_pipeline

logger = get_logger(__name__)


async def run_scheduled_publish(batch_size: int = 5) -> dict[str, Any]:
    """
    Chạy scheduled publish theo tenant qua orchestrator mode='scheduled'.

    Returns:
        dict: {claimed, processed, skipped, errors}
    """
    now_utc = datetime.now(timezone.utc)
    claimed = 0
    processed = 0
    skipped = 0
    errors: list[str] = []
    claimed = 0

    async with async_session_factory() as db:
        q = (
            select(ContentItem.tenant_id)
            .where(
                ContentItem.status == "approved",
                ContentItem.schedule_status == "scheduled",
                ContentItem.scheduled_at.is_not(None),
                ContentItem.scheduled_at <= now_utc,
            )
            .distinct()
            .limit(batch_size)
        )
        r = await db.execute(q)
        tenant_ids = [row[0] for row in r.all()]

    for tenant_id in tenant_ids:
        try:
            result = await run_drive_to_facebook_pipeline(
                tenant_id=tenant_id,
                options={
                    "mode": "scheduled",
                    "limit": batch_size,
                    "ingest": False,
                    "summarize": False,
                    "generate": False,
                    "approve": False,
                    "publish": True,
                    "metrics": True,
                },
            )
            claimed += int(result.get("claimed", 0))
            processed += int(result.get("processed", 0))
            skipped += int(result.get("skipped", 0))
            errors.extend(list(result.get("errors", [])))
        except Exception as err:
            skipped += 1
            errors.append(f"{tenant_id}: {err}")

    logger.info("scheduled_publish.done", processed=processed, skipped=skipped)
    return {
        "claimed": claimed,
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
    }

