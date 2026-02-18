"""
Scheduler auto-publish: đăng nội dung đã approved theo scheduled_at.
Chạy trong process FastAPI (single instance, laptop). Mỗi 60s tìm item due và gọi Facebook publish.
Tránh double publish: SELECT FOR UPDATE SKIP LOCKED.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory
from app.logging_config import get_logger
from app.models import ContentItem
from app.services.approval_service import log_audit_event
from app.services.facebook_publish_service import publish_post
from app.services.facebook_metrics_service import fetch_and_store_metrics, get_recent_success_publish_logs

logger = get_logger(__name__)

INTERVAL_SECONDS = 60
MAX_PUBLISH_ATTEMPTS = 3
RETRY_BACKOFF_MINUTES = 10
METRICS_INTERVAL_MINUTES = 360  # 6 giờ
METRICS_LOOKBACK_DAYS = 7

# Trạng thái scheduler (in-memory, single instance)
_scheduler_task: Optional[asyncio.Task[None]] = None
_metrics_task: Optional[asyncio.Task[None]] = None
_stop_event: Optional[asyncio.Event] = None
_last_tick_at: Optional[datetime] = None
_enabled = False


def get_scheduler_status() -> dict:
    """Trả về enabled, interval_seconds, last_tick_at. pending_count cần db."""
    return {
        "enabled": _enabled,
        "interval_seconds": INTERVAL_SECONDS,
        "last_tick_at": _last_tick_at.isoformat() if _last_tick_at else None,
        "pending_count": None,
    }


async def _pending_count(db: AsyncSession) -> int:
    """Số item đang chờ đăng: status=approved, schedule_status=scheduled."""
    q = select(func.count(ContentItem.id)).where(
        ContentItem.status == "approved",
        ContentItem.schedule_status == "scheduled",
    )
    r = await db.execute(q)
    return r.scalar() or 0


async def _tick() -> None:
    """Một vòng scheduler: lấy item due, lock, publish, cập nhật trạng thái."""
    global _last_tick_at
    _last_tick_at = datetime.now(timezone.utc)
    async with async_session_factory() as db:
        try:
            now = _last_tick_at
            q = (
                select(ContentItem)
                .where(
                    ContentItem.status == "approved",
                    ContentItem.schedule_status == "scheduled",
                    ContentItem.scheduled_at <= now,
                )
            )
            # PostgreSQL: FOR UPDATE SKIP LOCKED để chỉ một worker lấy được row
            q = q.with_for_update(skip_locked=True)
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
                await _publish_one(item.id, item.tenant_id)
        except Exception as e:
            logger.warning("scheduler.tick_error", error=str(e))
            await db.rollback()


async def _publish_one(content_id: UUID, tenant_id: UUID) -> None:
    """Publish một item; cập nhật schedule_status, retry theo chính sách."""
    async with async_session_factory() as db:
        try:
            r = await db.execute(
                select(ContentItem).where(
                    ContentItem.id == content_id,
                    ContentItem.tenant_id == tenant_id,
                )
            )
            item = r.scalar_one_or_none()
            if not item or item.schedule_status != "publishing":
                return
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
            now = datetime.now(timezone.utc)
            if error_message is None and log and log.status == "success":
                item.status = "published"
                item.schedule_status = "published"
                item.last_publish_at = now
                item.last_publish_error = None
                await db.commit()
                logger.info("scheduler.published", content_id=str(content_id))
                return
            # Thất bại: tăng attempts, backoff hoặc failed
            item.publish_attempts = (item.publish_attempts or 0) + 1
            item.last_publish_error = error_message
            item.last_publish_at = now
            if item.publish_attempts >= MAX_PUBLISH_ATTEMPTS:
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
                logger.warning("scheduler.failed_max_attempts", content_id=str(content_id))
            else:
                # Retry: đặt lại scheduled_at = now + (attempts * 10 phút)
                delta_minutes = item.publish_attempts * RETRY_BACKOFF_MINUTES
                item.scheduled_at = now + timedelta(minutes=delta_minutes)
                item.schedule_status = "scheduled"
                await db.commit()
                logger.info(
                    "scheduler.retry_scheduled",
                    content_id=str(content_id),
                    attempt=item.publish_attempts,
                    next_at=item.scheduled_at.isoformat(),
                )
        except Exception as e:
            logger.warning("scheduler.publish_one_error", content_id=str(content_id), error=str(e))
            await db.rollback()


async def _metrics_tick() -> None:
    """Một vòng thu thập metrics: lấy publish_logs success trong 7 ngày, gọi Graph API và lưu post_metrics."""
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
    """Vòng lặp metrics: chạy _metrics_tick mỗi METRICS_INTERVAL_MINUTES (chỉ posts đăng trong 7 ngày)."""
    global _stop_event
    await asyncio.sleep(60)  # Chạy lần đầu sau 1 phút
    while not _stop_event.is_set():
        try:
            await _metrics_tick()
        except Exception as e:
            logger.warning("scheduler.metrics_loop_error", error=str(e))
        await asyncio.sleep(METRICS_INTERVAL_MINUTES * 60)


async def _scheduler_loop() -> None:
    """Vòng lặp chính: mỗi INTERVAL_SECONDS gọi _tick()."""
    global _stop_event
    _stop_event = asyncio.Event()
    while not _stop_event.is_set():
        try:
            await _tick()
        except Exception as e:
            logger.warning("scheduler.loop_error", error=str(e))
        await asyncio.sleep(INTERVAL_SECONDS)


async def start_scheduler(app: object) -> None:
    """Khởi động scheduler + metrics worker (gọi từ lifespan startup)."""
    global _scheduler_task, _metrics_task, _enabled
    if _scheduler_task is not None:
        return
    _enabled = True
    _stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    _metrics_task = asyncio.create_task(_metrics_loop())
    logger.info("scheduler.started", interval_seconds=INTERVAL_SECONDS, metrics_interval_minutes=METRICS_INTERVAL_MINUTES)


async def stop_scheduler() -> None:
    """Dừng scheduler và metrics worker (gọi từ lifespan shutdown)."""
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
