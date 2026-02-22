"""Pipeline orchestration: Google Drive READY -> create content -> publish Facebook."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

import structlog.contextvars
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models import ContentAsset, ContentItem
from app.services.drive_service import list_ready_files, move_to_rejected
from app.services.facebook_publish_service import publish_post
from app.services.gdrive_dropzone import ingest_ready_assets

logger = get_logger(__name__)


@dataclass
class PipelineRunResult:
    """Kết quả nội bộ của một lần chạy pipeline."""

    processed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


def _safe_caption(asset: ContentAsset) -> str:
    """Tạo caption đơn giản từ metadata asset để publish ổn định."""
    file_name = (asset.file_name or "media").strip()
    asset_type = (asset.asset_type or "image").strip().lower()
    return (
        f"Noi dung tu dong tu Google Drive ({asset_type}): {file_name}. "
        "Vui long review quy trinh va thong tin lien he truoc khi su dung."
    )


async def _create_approved_content_for_asset(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    asset: ContentAsset,
) -> ContentItem:
    """Tạo content_item approved và gắn asset.content_id để publish được ngay."""
    now_utc = datetime.now(timezone.utc)
    title = f"[AUTO] {asset.file_name or asset.drive_file_id}"
    item = ContentItem(
        tenant_id=tenant_id,
        plan_id=None,
        title=title[:512],
        caption=_safe_caption(asset),
        hashtags="#automation #facebook #gdrive",
        status="approved",
        confidence_score=0.8,
        review_state="approved",
        approved_at=now_utc,
        require_media=True,
        primary_asset_type=(asset.asset_type or "image"),
    )
    db.add(item)
    await db.flush()

    asset.content_id = item.id
    db.add(asset)
    await db.flush()
    return item


async def run_drive_to_facebook_pipeline(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> PipelineRunResult:
    """
    Chạy full pipeline cho tenant:
    1) Scan READY folders
    2) Ingest idempotent về content_assets
    3) Với mỗi asset cached chưa upload -> tạo content + publish Facebook
    """
    correlation_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    result = PipelineRunResult()

    logger.info(
        "pipeline.drive_to_facebook.run_started",
        tenant_id=str(tenant_id),
        correlation_id=correlation_id,
    )

    # Step 1: Scan READY folder để có observability rõ ràng trong log.
    try:
        ready_items = list_ready_files()
        logger.info(
            "pipeline.drive_to_facebook.ready_scanned",
            tenant_id=str(tenant_id),
            ready_count=len(ready_items),
            correlation_id=correlation_id,
        )
    except Exception as err:
        msg = f"scan_ready_failed: {err}"
        result.errors.append(msg)
        logger.warning(
            "pipeline.drive_to_facebook.scan_ready_failed",
            tenant_id=str(tenant_id),
            error=str(err),
            correlation_id=correlation_id,
        )
        return result

    # Step 2: Đồng bộ Drive -> content_assets (cached/invalid/skipped).
    try:
        ingested, invalid, skipped = await ingest_ready_assets(db, tenant_id=tenant_id)
        logger.info(
            "pipeline.drive_to_facebook.ingest_done",
            tenant_id=str(tenant_id),
            ingested=ingested,
            invalid=invalid,
            skipped=skipped,
            correlation_id=correlation_id,
        )
    except Exception as err:
        msg = f"ingest_failed: {err}"
        result.errors.append(msg)
        logger.warning(
            "pipeline.drive_to_facebook.ingest_failed",
            tenant_id=str(tenant_id),
            error=str(err),
            correlation_id=correlation_id,
        )
        return result

    # Step 3: Process các asset khả dụng.
    q = (
        select(ContentAsset)
        .where(
            ContentAsset.tenant_id == tenant_id,
            ContentAsset.status == "cached",
        )
        .order_by(ContentAsset.created_at.asc())
    )
    r = await db.execute(q)
    assets = list(r.scalars().all())

    for asset in assets:
        if asset.status == "uploaded":
            result.skipped += 1
            continue
        if not asset.drive_file_id:
            result.skipped += 1
            continue

        try:
            content_item = await _create_approved_content_for_asset(
                db,
                tenant_id=tenant_id,
                asset=asset,
            )
            _, error_message, _ = await publish_post(
                db,
                tenant_id=tenant_id,
                content_id=content_item.id,
                actor="SYSTEM",
                use_latest_asset=False,
            )
            if error_message:
                result.skipped += 1
                result.errors.append(f"asset={asset.drive_file_id}: {error_message}")
                continue

            result.processed += 1
        except Exception as err:
            # Fail-safe: nếu pipeline fail trước khi vào publish service thì move sang REJECTED.
            try:
                move_to_rejected(asset.drive_file_id)
            except Exception:
                pass
            result.skipped += 1
            result.errors.append(f"asset={asset.drive_file_id}: {err}")
            logger.warning(
                "pipeline.drive_to_facebook.item_failed",
                tenant_id=str(tenant_id),
                asset_id=str(asset.id),
                drive_file_id=asset.drive_file_id,
                error=str(err),
                correlation_id=correlation_id,
            )

    logger.info(
        "pipeline.drive_to_facebook.run_done",
        tenant_id=str(tenant_id),
        processed=result.processed,
        skipped=result.skipped,
        error_count=len(result.errors),
        correlation_id=correlation_id,
    )
    return result

