"""
Đăng bài đã APPROVED lên Facebook Page qua Graph API.
Chỉ dùng Graph API, không headless; ghi publish_logs và audit events.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models import ContentItem, PublishLog
from app.services.approval_service import log_audit_event

logger = get_logger(__name__)

PLATFORM_FACEBOOK = "facebook"
GRAPH_BASE = "https://graph.facebook.com"
HTTP_TIMEOUT = 30.0
MAX_RETRIES = 2


async def publish_post(
    db: AsyncSession,
    tenant_id: UUID,
    content_id: UUID,
    actor: str = "HUMAN",
) -> Tuple[PublishLog, Optional[str]]:
    """
    Đăng một content_item lên Facebook Page (chỉ khi status == "approved").
    - Tạo PublishLog status=queued, ghi PUBLISH_REQUESTED.
    - Gọi Graph API POST /{page_id}/feed.
    - Cập nhật log success/fail, ghi PUBLISH_SUCCESS hoặc PUBLISH_FAIL.
    Trả về (publish_log, error_message). error_message chỉ có khi fail.
    """
    settings = get_settings()
    if not settings.facebook_page_id or not settings.facebook_access_token:
        raise ValueError("facebook_not_configured")

    # Load content, kiểm tra thuộc tenant và status == approved
    r = await db.execute(
        select(ContentItem).where(
            ContentItem.id == content_id,
            ContentItem.tenant_id == tenant_id,
        )
    )
    item = r.scalar_one_or_none()
    if not item:
        raise ValueError("content_not_found")
    if item.status != "approved":
        raise ValueError("content_not_approved")

    # Tạo log queued và audit PUBLISH_REQUESTED
    log = PublishLog(
        content_id=content_id,
        platform=PLATFORM_FACEBOOK,
        status="queued",
    )
    db.add(log)
    await db.flush()

    await log_audit_event(
        db,
        tenant_id=tenant_id,
        content_id=content_id,
        event_type="PUBLISH_REQUESTED",
        actor=actor,
        metadata_={"platform": PLATFORM_FACEBOOK},
    )

    # Nội dung bài: caption hoặc title + caption
    message = (item.caption or "").strip() or item.title
    if item.hashtags:
        message = f"{message}\n\n{item.hashtags}".strip()

    url = f"{GRAPH_BASE}/{settings.facebook_api_version}/{settings.facebook_page_id}/feed"
    payload = {
        "message": message,
        "access_token": settings.facebook_access_token,
    }

    last_error: Optional[str] = None
    http_status: Optional[int] = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.post(url, data=payload)
            http_status = resp.status_code
            if resp.status_code == 200:
                data = resp.json()
                post_id = data.get("id") or data.get("post_id")
                if not post_id and "id" in data:
                    post_id = str(data["id"])
                now = datetime.now(timezone.utc)
                log.status = "success"
                log.post_id = post_id
                log.published_at = now
                log.error_message = None
                item.status = "published"
                await db.flush()
                await log_audit_event(
                    db,
                    tenant_id=tenant_id,
                    content_id=content_id,
                    event_type="PUBLISH_SUCCESS",
                    actor=actor,
                    metadata_={"platform": PLATFORM_FACEBOOK, "post_id": post_id, "http_status": resp.status_code},
                )
                logger.info(
                    "facebook_publish.success",
                    content_id=str(content_id),
                    post_id=post_id,
                )
                return log, None
            # Lỗi từ API
            try:
                err_body = resp.json()
                err_msg = err_body.get("error", {}).get("message", resp.text) or resp.text
            except Exception:
                err_msg = resp.text or f"HTTP {resp.status_code}"
            last_error = err_msg
        except httpx.TimeoutException as e:
            last_error = f"Timeout: {e}"
            http_status = None
        except httpx.RequestError as e:
            last_error = str(e)
            resp_obj = getattr(e, "response", None)
            http_status = resp_obj.status_code if resp_obj is not None else None

        if attempt < MAX_RETRIES:
            logger.warning("facebook_publish.retry", attempt=attempt + 1, error=last_error)

    # Fail sau tất cả retry
    log.status = "fail"
    log.error_message = last_error
    log.published_at = None
    await db.flush()
    await log_audit_event(
        db,
        tenant_id=tenant_id,
        content_id=content_id,
        event_type="PUBLISH_FAIL",
        actor=actor,
        metadata_={
            "platform": PLATFORM_FACEBOOK,
            "http_status": http_status,
            "error": last_error,
        },
    )
    logger.warning("facebook_publish.fail", content_id=str(content_id), error=last_error)
    return log, last_error


async def list_publish_logs(
    db: AsyncSession,
    tenant_id: UUID,
    limit: int = 50,
) -> list[PublishLog]:
    """Lấy danh sách publish logs của tenant (qua content_items), mới nhất trước."""
    q = (
        select(PublishLog)
        .join(ContentItem, ContentItem.id == PublishLog.content_id)
        .where(ContentItem.tenant_id == tenant_id)
        .order_by(PublishLog.created_at.desc())
        .limit(limit)
    )
    r = await db.execute(q)
    return list(r.scalars().all())
