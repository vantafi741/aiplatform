"""Scheduler status response."""
from typing import Optional

from pydantic import BaseModel


class SchedulerStatusResponse(BaseModel):
    """GET /scheduler/status."""

    enabled: bool
    interval_seconds: int
    last_tick_at: Optional[str] = None
    pending_count: Optional[int] = None
