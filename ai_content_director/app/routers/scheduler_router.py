"""Scheduler status API."""
from fastapi import APIRouter, Depends

from app.db import get_db
from app.schemas.scheduler import SchedulerStatusResponse
from app.services.scheduler_service import get_scheduler_status_with_pending
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(
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
