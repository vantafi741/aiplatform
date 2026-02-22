"""Pipeline API: trigger Drive -> Facebook publish flow."""
from datetime import datetime, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import ContentItem
from app.services.facebook_publish_service import publish_post

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


class DriveToFacebookRunRequest(BaseModel):
    """Body cho endpoint run pipeline."""

    tenant_id: UUID = Field(..., description="Tenant UUID")


class DriveToFacebookRunResponse(BaseModel):
    """Response chuẩn cho pipeline run."""

    ok: bool = True
    processed: int = 0
    skipped: int = 0
    errors: List[str] = Field(default_factory=list)


@router.post("/drive_to_facebook/run", response_model=DriveToFacebookRunResponse)
async def run_drive_to_facebook(
    payload: DriveToFacebookRunRequest,
    db: AsyncSession = Depends(get_db),
) -> DriveToFacebookRunResponse:
    """
    DB-first pipeline runner:
    - Lấy tối đa 5 content_items đủ điều kiện scheduled publish.
    - Gọi publish service nội bộ cho từng item.
    - Cập nhật publish_attempts/last_publish_at/schedule_status/last_publish_error.
    """
    now_utc = datetime.now(timezone.utc)
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
    r = await db.execute(q)
    items = list(r.scalars().all())

    processed = 0
    skipped = 0
    errors: List[str] = []

    for item in items:
        item.publish_attempts = (item.publish_attempts or 0) + 1
        try:
            _, error_message, _ = await publish_post(
                db,
                tenant_id=payload.tenant_id,
                content_id=item.id,
                actor="SYSTEM",
                use_latest_asset=True,
            )
            if error_message:
                item.last_publish_error = error_message
                skipped += 1
                errors.append(f"{item.id}: {error_message}")
            else:
                item.last_publish_at = datetime.now(timezone.utc)
                item.schedule_status = "published"
                item.last_publish_error = None
                processed += 1
        except ValueError as err:
            item.last_publish_error = str(err)
            skipped += 1
            errors.append(f"{item.id}: {err}")
        except Exception as err:
            item.last_publish_error = str(err)
            skipped += 1
            errors.append(f"{item.id}: {err}")

        db.add(item)

    return DriveToFacebookRunResponse(
        ok=True,
        processed=processed,
        skipped=skipped,
        errors=errors,
    )

