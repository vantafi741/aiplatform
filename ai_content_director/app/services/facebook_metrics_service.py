"""
Thu thập metrics (reach, impressions, reactions, comments, shares) từ Facebook Graph API.
Lưu vào post_metrics; xử lý thiếu quyền hoặc lỗi (log + raw).
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models import ContentItem, PublishLog, PostMetrics
from app.services.approval_service import log_audit_event

logger = get_logger(__name__)

PLATFORM_FACEBOOK = "facebook"
GRAPH_BASE = "https://graph.facebook.com"
HTTP_TIMEOUT = 15.0

# Insights metrics (Page post). Một số cần pages_read_engagement / pages_read_user_content.
INSIGHTS_METRICS = "post_impressions,post_impressions_unique,post_reactions_by_type_total,post_clicks"


async def fetch_metrics_for_post(post_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Gọi Graph API lấy metrics cho post_id.
    Trả về (data_dict, error_message). data_dict có thể chứa insights và/hoặc engagement.
    """
    settings = get_settings()
    if not settings.facebook_access_token:
        return None, "facebook_not_configured"
    url = f"{GRAPH_BASE}/{settings.facebook_api_version}/{post_id}"
    params = {
        "access_token": settings.facebook_access_token,
        "fields": f"id,insights.metric({INSIGHTS_METRICS}),reactions.summary(total_count),comments.summary(total_count)",
    }
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(url, params=params)
    except httpx.RequestError as e:
        return None, str(e)
    try:
        data = resp.json()
    except Exception as e:
        return None, f"json_error: {e}"
    if resp.status_code != 200:
        err = data.get("error", {})
        msg = err.get("message", resp.text) or resp.text
        return data, msg  # Trả raw để lưu
    return data, None


def _parse_metrics_from_response(data: Dict[str, Any]) -> Dict[str, Optional[int]]:
    """Trích reach, impressions, reactions, comments, shares từ response Graph API."""
    out: Dict[str, Optional[int]] = {
        "reach": None,
        "impressions": None,
        "reactions": None,
        "comments": None,
        "shares": None,
    }
    if not data:
        return out
    # insights: list of { name, values: [ { value } ] }
    insights = data.get("insights", {}).get("data", []) if isinstance(data.get("insights"), dict) else []
    if not insights and isinstance(data.get("insights"), list):
        insights = data.get("insights", [])
    for item in insights:
        name = item.get("name")
        values = item.get("values", [])
        val = values[0].get("value") if values else None
        if name == "post_impressions_unique":
            out["reach"] = int(val) if val is not None else None
        elif name == "post_impressions":
            out["impressions"] = int(val) if val is not None else None
        elif name == "post_reactions_by_type_total":
            if isinstance(val, dict):
                out["reactions"] = sum(int(v) for v in val.values() if isinstance(v, (int, float)))
            elif val is not None:
                out["reactions"] = int(val)
    # reactions.summary(total_count), comments.summary(total_count)
    reactions = data.get("reactions", {})
    if isinstance(reactions, dict):
        total = reactions.get("summary", {}).get("total_count")
        if total is not None and out["reactions"] is None:
            out["reactions"] = int(total)
    comments = data.get("comments", {})
    if isinstance(comments, dict):
        total = comments.get("summary", {}).get("total_count")
        if total is not None:
            out["comments"] = int(total)
    return out


async def fetch_and_store_metrics(
    db: AsyncSession,
    tenant_id: UUID,
    content_id: UUID,
    publish_log_id: UUID,
    post_id: str,
    platform: str = PLATFORM_FACEBOOK,
) -> Tuple[PostMetrics, bool]:
    """
    Gọi fetch_metrics_for_post, lưu vào post_metrics. Ghi audit METRICS_FETCH_SUCCESS hoặc METRICS_FETCH_FAIL.
    Trả về (bản ghi PostMetrics, success: True nếu không lỗi).
    """
    data, error = await fetch_metrics_for_post(post_id)
    now = datetime.now(timezone.utc)
    parsed = _parse_metrics_from_response(data) if data else {}
    raw: Optional[Dict[str, Any]] = data
    if error:
        raw = (data or {}) | {"_error": error, "_status": "fail"}
        log_metadata: Dict[str, Any] = {"post_id": post_id, "error": error}
        await log_audit_event(
            db,
            tenant_id=tenant_id,
            content_id=content_id,
            event_type="METRICS_FETCH_FAIL",
            actor="SYSTEM",
            metadata_=log_metadata,
        )
        logger.warning("facebook_metrics.fetch_fail", post_id=post_id, error=error)
    else:
        await log_audit_event(
            db,
            tenant_id=tenant_id,
            content_id=content_id,
            event_type="METRICS_FETCH_SUCCESS",
            actor="SYSTEM",
            metadata_={"post_id": post_id, "reach": parsed.get("reach"), "impressions": parsed.get("impressions")},
        )
        logger.info("facebook_metrics.fetch_ok", post_id=post_id)
    row = PostMetrics(
        tenant_id=tenant_id,
        content_id=content_id,
        publish_log_id=publish_log_id,
        platform=platform,
        fetched_at=now,
        reach=parsed.get("reach"),
        impressions=parsed.get("impressions"),
        reactions=parsed.get("reactions"),
        comments=parsed.get("comments"),
        shares=parsed.get("shares"),
        raw=raw,
    )
    db.add(row)
    await db.flush()
    return row, error is None


# Giới hạn an toàn cho fetch-now thủ công
FETCH_NOW_MAX_DAYS = 30
FETCH_NOW_MAX_LIMIT = 50


async def fetch_now_metrics(
    db: AsyncSession,
    tenant_id: UUID,
    days: int = 7,
    limit: int = 20,
) -> Tuple[int, int, int]:
    """
    Thu thập metrics ngay cho các bài đăng thành công của tenant trong `days` ngày (tối đa limit bài).
    days tối đa 30, limit tối đa 50.
    Trả về (fetched, success, fail).
    """
    days = min(days, FETCH_NOW_MAX_DAYS)
    limit = min(limit, FETCH_NOW_MAX_LIMIT)
    rows = await get_recent_success_publish_logs(
        db,
        within_days=days,
        tenant_id=tenant_id,
        limit=limit,
    )
    success = 0
    fail = 0
    for tid, content_id, publish_log_id, post_id in rows:
        try:
            _, ok = await fetch_and_store_metrics(
                db,
                tenant_id=tid,
                content_id=content_id,
                publish_log_id=publish_log_id,
                post_id=post_id,
            )
            if ok:
                success += 1
            else:
                fail += 1
        except Exception as e:
            logger.warning("facebook_metrics.fetch_now_one_error", post_id=post_id, error=str(e))
            fail += 1
        await db.commit()
    return len(rows), success, fail


async def get_recent_success_publish_logs(
    db: AsyncSession,
    within_days: int = 7,
    tenant_id: Optional[UUID] = None,
    limit: Optional[int] = None,
) -> list[Tuple[UUID, UUID, UUID, str]]:
    """
    Lấy các publish_log có status=success, published_at trong within_days gần đây.
    Nếu tenant_id: chỉ tenant đó. Nếu limit: giới hạn số dòng.
    Trả về list (tenant_id, content_id, publish_log_id, post_id).
    """
    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(days=within_days)
    q = (
        select(PublishLog, ContentItem.tenant_id)
        .join(ContentItem, ContentItem.id == PublishLog.content_id)
        .where(
            PublishLog.status == "success",
            PublishLog.post_id.isnot(None),
            PublishLog.published_at >= since,
        )
    )
    if tenant_id is not None:
        q = q.where(ContentItem.tenant_id == tenant_id)
    q = q.order_by(PublishLog.published_at.desc())
    if limit is not None:
        q = q.limit(limit)
    r = await db.execute(q)
    rows = r.all()
    return [(tid, pl.content_id, pl.id, pl.post_id) for (pl, tid) in rows if pl.post_id]


async def get_kpi_summary(
    db: AsyncSession,
    tenant_id: UUID,
    days: int = 7,
) -> Tuple[Dict[str, int], list[Dict[str, Any]]]:
    """
    Tổng hợp KPI từ post_metrics trong `days` gần đây (theo fetched_at).
    Lấy bản ghi mới nhất theo publish_log_id cho mỗi post; tổng và danh sách post.
    Trả về (totals_dict, posts_list). totals: reach, impressions, reactions, comments, shares.
    """
    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        select(PostMetrics, PublishLog.post_id)
        .join(PublishLog, PublishLog.id == PostMetrics.publish_log_id)
        .where(
            PostMetrics.tenant_id == tenant_id,
            PostMetrics.fetched_at >= since,
        )
        .order_by(PostMetrics.fetched_at.desc())
    )
    r = await db.execute(q)
    rows = r.all()
    # Lấy bản ghi mới nhất theo publish_log_id
    by_log: Dict[UUID, Any] = {}
    for pm, post_id in rows:
        if pm.publish_log_id not in by_log:
            by_log[pm.publish_log_id] = (pm, post_id)
    totals = {"reach": 0, "impressions": 0, "reactions": 0, "comments": 0, "shares": 0}
    posts: list[Dict[str, Any]] = []
    for (pm, post_id) in by_log.values():
        if pm.reach is not None:
            totals["reach"] += pm.reach
        if pm.impressions is not None:
            totals["impressions"] += pm.impressions
        if pm.reactions is not None:
            totals["reactions"] += pm.reactions
        if pm.comments is not None:
            totals["comments"] += pm.comments
        if pm.shares is not None:
            totals["shares"] += pm.shares
        posts.append({
            "post_id": post_id,
            "fetched_at": pm.fetched_at.isoformat() if pm.fetched_at else None,
            "reach": pm.reach,
            "impressions": pm.impressions,
            "reactions": pm.reactions,
            "comments": pm.comments,
            "shares": pm.shares,
        })
    return totals, posts
