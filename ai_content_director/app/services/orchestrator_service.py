"""Single Source of Truth orchestration cho luong Drive -> Facebook."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select

from app.db import async_session_factory
from app.logging_config import get_logger
from app.models import ContentAsset, ContentItem
from app.services.asset_summary_service import get_or_create_asset_summary
from app.services.facebook_metrics_service import fetch_and_store_metrics
from app.services.facebook_publish_service import publish_post
from app.services.gdrive_dropzone import ingest_ready_assets

logger = get_logger(__name__)


def _options_with_defaults(options: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize options cho pipeline run."""
    opts = dict(options or {})
    return {
        "mode": str(opts.get("mode", "full")),
        "limit": int(opts.get("limit", 5)),
        "ingest": bool(opts.get("ingest", True)),
        "summarize": bool(opts.get("summarize", True)),
        "generate": bool(opts.get("generate", True)),
        "approve": bool(opts.get("approve", True)),
        "publish": bool(opts.get("publish", True)),
        "metrics": bool(opts.get("metrics", True)),
    }


def _build_caption(asset: ContentAsset, summary_text: str | None) -> str:
    """Tao caption an toan de publish tu asset + summary context."""
    base = f"Noi dung tu dong tu Google Drive: {asset.file_name or asset.drive_file_id}."
    if summary_text:
        return f"{base}\nTom tat media: {summary_text[:1200]}"
    return base


async def _run_scheduled_publish_for_tenant(
    tenant_id: UUID,
    *,
    limit: int,
) -> dict[str, Any]:
    """
    Nhánh publish scheduled cho tenant.

    Dùng cho scheduler/manual tick để tránh duplicate logic ở nhiều nơi.
    """
    now_utc = datetime.now(timezone.utc)
    processed = 0
    skipped = 0
    claimed = 0
    metrics_fetched = 0
    errors: list[str] = []

    async with async_session_factory() as db:
        q = (
            select(ContentItem)
            .where(
                ContentItem.tenant_id == tenant_id,
                ContentItem.status == "approved",
                ContentItem.schedule_status == "scheduled",
                ContentItem.scheduled_at.is_not(None),
                ContentItem.scheduled_at <= now_utc,
                or_(
                    ContentItem.publish_attempts.is_(None),
                    ContentItem.publish_attempts < 3,
                ),
            )
            .order_by(ContentItem.scheduled_at.asc(), ContentItem.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        result = await db.execute(q)
        items = list(result.scalars().all())
        claimed = len(items)

        logger.info(
            "orchestrator.step.publish_selected",
            tenant_id=str(tenant_id),
            count=claimed,
            mode="scheduled",
        )

        for item in items:
            item.publish_attempts = (item.publish_attempts or 0) + 1
            item.schedule_status = "processing"
            db.add(item)
        await db.commit()

    for item_id in [str(i.id) for i in items]:
        async with async_session_factory() as db:
            row = await db.execute(select(ContentItem).where(ContentItem.id == item_id))
            item = row.scalar_one_or_none()
            if not item:
                skipped += 1
                errors.append(f"{item_id}: content_not_found")
                await db.commit()
                continue
            if item.schedule_status != "processing":
                skipped += 1
                errors.append(f"{item_id}: invalid_schedule_status({item.schedule_status})")
                await db.commit()
                continue

            try:
                publish_log, error_message, _ = await publish_post(
                    db,
                    tenant_id=item.tenant_id,
                    content_id=item.id,
                    actor="SYSTEM",
                    use_latest_asset=True,
                )
                if error_message:
                    item.schedule_status = "failed"
                    item.last_publish_error = error_message
                    skipped += 1
                    errors.append(f"{item.id}: {error_message}")
                else:
                    item.schedule_status = "published"
                    item.last_publish_at = datetime.now(timezone.utc)
                    item.last_publish_error = None
                    processed += 1
                    if publish_log and publish_log.post_id:
                        try:
                            _metric_row, metric_ok = await fetch_and_store_metrics(
                                db,
                                tenant_id=item.tenant_id,
                                content_id=item.id,
                                publish_log_id=publish_log.id,
                                post_id=publish_log.post_id,
                            )
                            if metric_ok:
                                metrics_fetched += 1
                        except Exception as metric_err:
                            errors.append(f"{item.id}: metrics_failed({metric_err})")
                db.add(item)
                await db.commit()
            except Exception as err:
                await db.rollback()
                skipped += 1
                errors.append(f"{item_id}: {err}")

    return {
        "ingested": 0,
        "summarized": 0,
        "generated": 0,
        "approved": 0,
        "published": processed,
        "metrics_fetched": metrics_fetched,
        "claimed": claimed,
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "now_utc": now_utc.isoformat(),
        "ok": True,
    }


async def run_drive_to_facebook_pipeline(
    tenant_id: UUID,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Single source of truth cho orchestrator Drive -> Summary -> Generate -> Approve -> Publish -> Metrics.

    Args:
        tenant_id: tenant cần chạy pipeline.
        options: dict options (mode, limit, ingest, summarize, generate, approve, publish, metrics).
                 - mode='full' (default): chạy full asset pipeline.
                 - mode='scheduled': chỉ xử lý content_items đã scheduled/approved.

    Returns:
        dict kết quả chuẩn:
        {ingested, summarized, generated, approved, published, metrics_fetched, errors, ...}
    """
    opts = _options_with_defaults(options)
    now_utc = datetime.now(timezone.utc)
    errors: list[str] = []

    if opts["mode"] == "scheduled":
        return await _run_scheduled_publish_for_tenant(
            tenant_id=tenant_id,
            limit=opts["limit"],
        )

    ingested = 0
    summarized = 0
    generated = 0
    approved = 0
    published = 0
    metrics_fetched = 0
    skipped = 0
    count_invalid = 0
    count_skipped_ingest = 0

    logger.info(
        "orchestrator.pipeline.start",
        tenant_id=str(tenant_id),
        options=opts,
    )

    async with async_session_factory() as db:
        if opts["ingest"]:
            try:
                i, invalid, s = await ingest_ready_assets(db, tenant_id=tenant_id)
                ingested += i
                count_invalid += invalid
                count_skipped_ingest += s
                await db.commit()
                logger.info(
                    "orchestrator.step.ingest_done",
                    tenant_id=str(tenant_id),
                    ingested=i,
                    invalid=invalid,
                    skipped=s,
                )
            except Exception as err:
                await db.rollback()
                errors.append(f"ingest_failed: {err}")
                logger.warning(
                    "orchestrator.step.ingest_failed",
                    tenant_id=str(tenant_id),
                    error=str(err),
                )

        q = (
            select(ContentAsset)
            .where(
                ContentAsset.tenant_id == tenant_id,
                ContentAsset.status == "cached",
                ContentAsset.content_id.is_(None),
            )
            .order_by(ContentAsset.created_at.asc())
            .limit(opts["limit"])
        )
        r = await db.execute(q)
        assets = list(r.scalars().all())
        logger.info(
            "orchestrator.step.assets_selected",
            tenant_id=str(tenant_id),
            count=len(assets),
        )

        for asset in assets:
            summary_text: str | None = None
            if opts["summarize"]:
                try:
                    summary_row, _cached = await get_or_create_asset_summary(
                        db,
                        tenant_id=tenant_id,
                        asset_id=asset.id,
                    )
                    summary_text = summary_row.summary
                    summarized += 1
                except Exception as err:
                    errors.append(f"{asset.id}: summarize_failed({err})")

            if not opts["generate"]:
                skipped += 1
                continue

            try:
                content = ContentItem(
                    tenant_id=tenant_id,
                    plan_id=None,
                    title=f"[AUTO] {asset.file_name or asset.drive_file_id}"[:512],
                    caption=_build_caption(asset, summary_text),
                    hashtags="#automation #pipeline #facebook",
                    status="approved" if opts["approve"] else "draft",
                    confidence_score=0.80,
                    review_state="approved" if opts["approve"] else "needs_review",
                    approved_at=datetime.now(timezone.utc) if opts["approve"] else None,
                    require_media=True,
                    primary_asset_type=(asset.asset_type or "image"),
                    schedule_status="processing" if opts["publish"] else "scheduled",
                    scheduled_at=now_utc,
                )
                db.add(content)
                await db.flush()
                generated += 1
                if opts["approve"]:
                    approved += 1

                asset.content_id = content.id
                db.add(asset)
                await db.flush()

                if opts["publish"] and opts["approve"]:
                    publish_log, error_message, _ = await publish_post(
                        db,
                        tenant_id=tenant_id,
                        content_id=content.id,
                        actor="SYSTEM",
                        use_latest_asset=False,
                    )
                    if error_message:
                        content.schedule_status = "failed"
                        content.last_publish_error = error_message
                        skipped += 1
                        errors.append(f"{content.id}: {error_message}")
                    else:
                        content.schedule_status = "published"
                        content.last_publish_at = datetime.now(timezone.utc)
                        content.last_publish_error = None
                        published += 1
                        if opts["metrics"] and publish_log and publish_log.post_id:
                            try:
                                _metric_row, metric_ok = await fetch_and_store_metrics(
                                    db,
                                    tenant_id=tenant_id,
                                    content_id=content.id,
                                    publish_log_id=publish_log.id,
                                    post_id=publish_log.post_id,
                                )
                                if metric_ok:
                                    metrics_fetched += 1
                            except Exception as metric_err:
                                errors.append(f"{content.id}: metrics_failed({metric_err})")

                db.add(content)
                await db.commit()
            except Exception as err:
                await db.rollback()
                skipped += 1
                errors.append(f"{asset.id}: pipeline_item_failed({err})")

    logger.info(
        "orchestrator.pipeline.done",
        tenant_id=str(tenant_id),
        ingested=ingested,
        summarized=summarized,
        generated=generated,
        approved=approved,
        published=published,
        metrics_fetched=metrics_fetched,
        errors=len(errors),
    )
    return {
        "ok": True,
        "ingested": ingested,
        "count_invalid": count_invalid,
        "count_skipped_ingest": count_skipped_ingest,
        "summarized": summarized,
        "generated": generated,
        "approved": approved,
        "published": published,
        "metrics_fetched": metrics_fetched,
        "processed": published,
        "skipped": skipped,
        "errors": errors,
        "now_utc": now_utc.isoformat(),
    }
