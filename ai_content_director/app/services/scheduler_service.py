"""
Scheduler auto-publish: đăng nội dung đã approved theo scheduled_at.
Chạy trong process FastAPI (single instance, laptop). Mỗi 60s tìm item due và gọi Facebook publish.
Tránh double publish: SELECT FOR UPDATE SKIP LOCKED.
"""
import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory
from app.logging_config import get_logger
from app.models import ContentItem
from app.services.facebook_metrics_service import fetch_and_store_metrics, get_recent_success_publish_logs
from app.services.scheduled_publish_worker import run_scheduled_publish

logger = get_logger(__name__)

INTERVAL_SECONDS = 60
METRICS_INTERVAL_MINUTES = 360  # 6 giờ
METRICS_LOOKBACK_DAYS = 7

# Trạng thái scheduler (in-memory, single instance)
_scheduler_task: Optional[asyncio.Task[None]] = None
_metrics_task: Optional[asyncio.Task[None]] = None
_stop_event: Optional[asyncio.Event] = None
_last_tick_at: Optional[datetime] = None
_enabled = False


def is_internal_scheduler_enabled() -> bool:
    """
    Chỉ bật scheduler nội bộ khi có explicit opt-in.

    Mặc định OFF để tránh double-run với n8n control-plane.
    """
    return os.getenv("ENABLE_INTERNAL_SCHEDULER", "0").strip() == "1"


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
    """Một vòng scheduler: gọi worker publish DB-first."""
    global _last_tick_at
    _last_tick_at = datetime.now(timezone.utc)
    try:
        result = await run_scheduled_publish(batch_size=5)
        logger.info(
            "scheduler.tick",
            claimed=result.get("claimed", 0),
            processed=result.get("processed", 0),
            skipped=result.get("skipped", 0),
        )
    except Exception as e:
        logger.warning("scheduled_publish.tick_failed", error=str(e))


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
    if not is_internal_scheduler_enabled():
        _enabled = False
        logger.info(
            "scheduler.disabled",
            reason="Scheduler disabled (n8n control-plane)",
            enable_internal_scheduler=os.getenv("ENABLE_INTERNAL_SCHEDULER", "0"),
        )
        return
    _enabled = True
    _stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    _metrics_task = asyncio.create_task(_metrics_loop())
    logger.warning(
        "scheduler.started_internal",
        interval_seconds=INTERVAL_SECONDS,
        metrics_interval_minutes=METRICS_INTERVAL_MINUTES,
        policy="Internal scheduler enabled; ensure n8n tick is disabled to avoid double-run",
    )


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
