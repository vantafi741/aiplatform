"""
Materialize plan 30 ngày thành content_items: scheduled_at, caption, channel, content_type, require_media.
Idempotent: nếu đã có content_items cho plan_id thì không tạo trùng.
"""
from datetime import date, datetime, time, timedelta
from typing import List
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models import ContentItem, ContentPlan

logger = get_logger(__name__)


def _parse_time(s: str) -> time:
    """Parse "HH:MM" hoặc "HH:MM:SS" thành time."""
    parts = s.strip().split(":")
    h = int(parts[0]) if len(parts) > 0 else 9
    m = int(parts[1]) if len(parts) > 1 else 0
    sec = int(parts[2]) if len(parts) > 2 else 0
    return time(h, m, sec)


def _scheduled_at_for_day(
    start_date: date,
    day_offset: int,
    posting_hours: List[time],
    tz_name: str,
) -> datetime:
    """Tính scheduled_at = start_date + day_offset, giờ lấy round-robin từ posting_hours."""
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Asia/Ho_Chi_Minh")
    d = start_date + timedelta(days=day_offset)
    hour_index = day_offset % len(posting_hours) if posting_hours else 0
    t = posting_hours[hour_index] if posting_hours else time(9, 0)
    return datetime.combine(d, t, tzinfo=tz)


async def materialize_plan(
    db: AsyncSession,
    plan_id: UUID,
    tenant_id: UUID,
    timezone_str: str,
    posting_hours: List[str],
    start_date: date,
    channel: str,
    default_status: str,
) -> tuple[int, List[UUID]]:
    """
    Từ plan_json (30 entries) tạo 30 content_items.
    Idempotent: nếu đã có content_items với plan_id thì trả về danh sách hiện có, count_created=0.
    Returns (count_created, content_item_ids).
    """
    r = await db.execute(
        select(ContentPlan).where(
            ContentPlan.id == plan_id,
            ContentPlan.tenant_id == tenant_id,
        )
    )
    plan = r.scalar_one_or_none()
    if not plan:
        raise ValueError("plan_not_found")

    plan_json = getattr(plan, "plan_json", None)
    if not plan_json or not isinstance(plan_json, list):
        raise ValueError("plan_has_no_plan_json")

    entries = plan_json[:30]
    if len(entries) < 30:
        raise ValueError("plan_json_insufficient_entries")

    # Idempotent: đã có items cho plan_id thì không tạo thêm
    count_q = select(func.count(ContentItem.id)).where(ContentItem.plan_id == plan_id)
    r = await db.execute(count_q)
    existing_count = r.scalar() or 0
    if existing_count >= 30:
        q_items = (
            select(ContentItem.id)
            .where(ContentItem.plan_id == plan_id)
            .order_by(ContentItem.scheduled_at)
        )
        r = await db.execute(q_items)
        ids = [row[0] for row in r.all()]
        logger.info(
            "plan_materialize.idempotent",
            plan_id=str(plan_id),
            tenant_id=str(tenant_id),
            existing_count=existing_count,
        )
        return 0, ids[:30]

    times: List[time] = []
    for s in (posting_hours or ["09:00"]):
        try:
            times.append(_parse_time(s))
        except (ValueError, IndexError):
            times.append(time(9, 0))

    tz_name = timezone_str or "Asia/Ho_Chi_Minh"
    created_ids: List[UUID] = []

    for i, entry in enumerate(entries):
        day_offset = i
        day_number = int(entry.get("day_number") or (i + 1))
        topic = entry.get("topic") or f"Chủ đề ngày {day_number}"
        content_angle = entry.get("content_angle") or ""
        caption = entry.get("content_angle") or entry.get("caption") or topic
        content_type_raw = (entry.get("content_type") or "text").strip().lower()
        if content_type_raw in ("image", "video"):
            content_type = content_type_raw
            require_media = True
            primary_asset_type = content_type_raw
        else:
            content_type = "text"
            require_media = False
            primary_asset_type = None

        scheduled_at = _scheduled_at_for_day(start_date, day_offset, times, tz_name)
        title = topic

        item = ContentItem(
            tenant_id=tenant_id,
            plan_id=plan_id,
            title=title,
            caption=caption,
            hashtags=None,
            status=default_status,
            scheduled_at=scheduled_at,
            channel=channel,
            content_type=content_type,
            require_media=require_media,
            primary_asset_type=primary_asset_type,
        )
        db.add(item)
        await db.flush()
        created_ids.append(item.id)

    logger.info(
        "plan_materialize.done",
        plan_id=str(plan_id),
        tenant_id=str(tenant_id),
        count_created=len(created_ids),
    )
    return len(created_ids), created_ids
