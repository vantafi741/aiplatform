"""
Scheduler auto-publish: đăng nội dung đã approved theo scheduled_at.
Chạy trong process FastAPI. Query: status=approved, scheduled_at <= now(), channel=facebook.
ENV: SCHEDULER_ENABLED, SCHEDULER_INTERVAL_SECONDS, SCHEDULER_TENANT_ID, PUBLISH_MAX_RETRIES.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session_factory
from app.logging_config import get_logger
from app.models import ContentItem
from app.services.approval_service import log_audit_event
from app.services.facebook_publish_service import publish_post
from app.services.facebook_metrics_service import fetch_and_store_metrics, get_recent_success_publish_logs

logger = get_logger(__name__)

RETRY_BACKOFF_MINUTES = 10
METRICS_INTERVAL_MINUTES = 360
METRICS_LOOKBACK_DAYS = 7

_scheduler_task: Optional[asyncio.Task[None]] = None
_metrics_task: Optional[asyncio.Task[None]] = None
_stop_event: Optional[asyncio.Event] = None
_last_tick_at: Optional[datetime] = None
_enabled = False


def get_scheduler_status() -> dict:
    """Trả về enabled, interval_seconds, last_tick_at. pending_count cần db."""
    settings = get_settings()
    return {
        "enabled": _enabled,
        "interval_seconds": settings.scheduler_interval_seconds,
        "last_tick_at": _last_tick_at.isoformat() if _last_tick_at else None,
        "pending_count": None,
    }


async def _pending_count(db: AsyncSession) -> int:
    """Số item đang chờ đăng: status=approved, scheduled_at <= now(), channel=facebook."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    q = select(func.count(ContentItem.id)).where(
        ContentItem.status == "approved",
        ContentItem.scheduled_at <= now,
        ContentItem.scheduled_at.isnot(None),
    )
    if settings.scheduler_tenant_id:
        try:
            tid = UUID(settings.scheduler_tenant_id)
            q = q.where(ContentItem.tenant_id == tid)
        except ValueError:
            pass
    q = q.where((ContentItem.channel == "facebook") | (ContentItem.channel.is_(None)))
    r = await db.execute(q)
    return r.scalar() or 0


async def _tick() -> None:
    """Một vòng scheduler: lấy item due (approved, scheduled_at <= now, channel=facebook), lock, publish."""
    global _last_tick_at
    settings = get_settings()
    if not settings.scheduler_enabled:
        return
    _last_tick_at = datetime.now(timezone.utc)
    logger.info("scheduler.tick", at=_last_tick_at.isoformat())
    async with async_session_factory() as db:
        try:
            now = _last_tick_at
            q = (
                select(ContentItem)
                .where(
                    ContentItem.status == "approved",
                    ContentItem.scheduled_at <= now,
                    ContentItem.scheduled_at.isnot(None),
                )
            )
            if settings.scheduler_tenant_id:
                try:
                    tid = UUID(settings.scheduler_tenant_id)
                    q = q.where(ContentItem.tenant_id == tid)
                except ValueError:
                    pass
            q = q.where((ContentItem.channel == "facebook") | (ContentItem.channel.is_(None)))
            q = q.with_for_update(skip_locked=True)
            q = q.limit(10)
            r = await db.execute(q)
            due_items = list(r.scalars().all())
            if not due_items:
                await db.commit()
                return
            for item in due_items:
                item.schedule_status = "publishing"
                await db.flush()
            await db.commit()
            for item in due_items:
                logger.info("scheduler.claimed", content_id=str(item.id), tenant_id=str(item.tenant_id))
                await _publish_one(item.id, item.tenant_id)
        except Exception as e:
            logger.warning("scheduler.tick_error", error=str(e))
            await db.rollback()


async def _publish_one(content_id: UUID, tenant_id: UUID) -> None:
    """Publish một item; cập nhật status, external_post_id, publish_attempts, last_error, publish_failed."""
    settings = get_settings()
    max_retries = settings.publish_max_retries
    async with async_session_factory() as db:
        try:
            r = await db.execute(
                select(ContentItem).where(
                    ContentItem.id == content_id,
                    ContentItem.tenant_id == tenant_id,
                )
            )
            item = r.scalar_one_or_none()
            if not item:
                return
            if item.status == "published":
                return
            if item.schedule_status != "publishing":
                return
            now = datetime.now(timezone.utc)
            item.publish_attempts = (item.publish_attempts or 0) + 1
            item.last_publish_attempt_at = now
            await db.flush()
            try:
                log, error_message = await publish_post(
                    db,
                    tenant_id=tenant_id,
                    content_id=content_id,
                    actor="SYSTEM",
                    use_latest_asset=True,
                )
            except ValueError as e:
                error_message = str(e)
                log = None
            if error_message is None and log and log.status == "success":
                item.status = "published"
                item.schedule_status = "published"
                item.last_publish_at = now
                item.last_publish_error = None
                if log and log.post_id:
                    item.external_post_id = log.post_id
                await db.commit()
                logger.info("scheduler.published", content_id=str(content_id), post_id=log.post_id if log else None)
                return
            item.last_publish_error = error_message
            if item.publish_attempts >= max_retries:
                item.status = "publish_failed"
                item.schedule_status = "failed"
                await log_audit_event(
                    db,
                    tenant_id=tenant_id,
                    content_id=content_id,
                    event_type="PUBLISH_FAIL",
                    actor="SYSTEM",
                    metadata_={"reason": "scheduler_max_attempts", "error": error_message},
                )
                await db.commit()
                logger.warning("scheduler.failed", content_id=str(content_id), attempts=item.publish_attempts)
            else:
                delta_minutes = item.publish_attempts * RETRY_BACKOFF_MINUTES
                item.scheduled_at = now + timedelta(minutes=delta_minutes)
                item.schedule_status = "scheduled"
                item.status = "approved"
                await db.commit()
                logger.info(
                    "scheduler.retry_scheduled",
                    content_id=str(content_id),
                    attempt=item.publish_attempts,
                    next_at=item.scheduled_at.isoformat() if item.scheduled_at else None,
                )
        except Exception as e:
            logger.warning("scheduler.publish_one_error", content_id=str(content_id), error=str(e))
            await db.rollback()


async def _metrics_tick() -> None:
    """Một vòng thu thập metrics."""
    async with async_session_factory() as db:
        try:
            rows = await get_recent_success_publish_logs(db, within_days=METRICS_LOOKBACK_DAYS)
            for tenant_id, content_id, publish_log_id, post_id in rows:
                try:
                    await fetch_and_store_metrics(
                        db,
                        tenant_id=tenant_id,
                        content_id=content_id,
                        publish_log_id=publish_log_id,
                        post_id=post_id,
                    )
                    await db.commit()
                except Exception as e:
                    logger.warning("scheduler.metrics_one_error", post_id=post_id, error=str(e))
                    await db.rollback()
        except Exception as e:
            logger.warning("scheduler.metrics_tick_error", error=str(e))
            await db.rollback()


async def _metrics_loop() -> None:
    global _stop_event
    await asyncio.sleep(60)
    while not _stop_event.is_set():
        try:
            await _metrics_tick()
        except Exception as e:
            logger.warning("scheduler.metrics_loop_error", error=str(e))
        await asyncio.sleep(METRICS_INTERVAL_MINUTES * 60)


async def _scheduler_loop() -> None:
    global _stop_event
    _stop_event = asyncio.Event()
    settings = get_settings()
    interval = max(1, settings.scheduler_interval_seconds)
    while not _stop_event.is_set():
        try:
            await _tick()
        except Exception as e:
            logger.warning("scheduler.loop_error", error=str(e))
        await asyncio.sleep(interval)


async def start_scheduler(app: object) -> None:
    """Khởi động scheduler + metrics worker (gọi từ lifespan startup)."""
    global _scheduler_task, _metrics_task, _enabled
    settings = get_settings()
    if _scheduler_task is not None:
        return
    _enabled = settings.scheduler_enabled
    _stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    _metrics_task = asyncio.create_task(_metrics_loop())
    logger.info(
        "scheduler.started",
        enabled=_enabled,
        interval_seconds=settings.scheduler_interval_seconds,
        metrics_interval_minutes=METRICS_INTERVAL_MINUTES,
    )


async def stop_scheduler() -> None:
    """Dừng scheduler và metrics worker."""
    global _scheduler_task, _metrics_task, _stop_event, _enabled
    _enabled = False
    if _stop_event:
        _stop_event.set()
    for task in (_scheduler_task, _metrics_task):
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    _scheduler_task = None
    _metrics_task = None
    logger.info("scheduler.stopped")


async def get_scheduler_status_with_pending(db: AsyncSession) -> dict:
    """Trả về status kèm pending_count từ db."""
    count = await _pending_count(db)
    out = get_scheduler_status()
    out["pending_count"] = count
    return out
