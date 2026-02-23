"""Scheduler status response."""
from typing import Optional

from pydantic import BaseModel


class SchedulerStatusResponse(BaseModel):
    """GET /scheduler/status."""

    enabled: bool
    interval_seconds: int
    last_tick_at: Optional[str] = None
    pending_count: Optional[int] = None


class SchedulerRunPublishTickRequest(BaseModel):
    """Body cho POST /api/scheduler/run_publish_tick."""

    batch_size: int = 5
    tenant_id: Optional[str] = None


class SchedulerRunPublishTickResponse(BaseModel):
    """Response cho manual run publish tick."""

    ok: bool
    processed: int
    skipped: int
    errors: list[str]
    now_utc: str
