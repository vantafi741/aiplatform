"""Publish lên Facebook (Graph API) + xem publish logs."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.logging_config import get_logger
from app.schemas.publish import (
    PublishFacebookRequest,
    PublishFacebookResponse,
    PublishLogOut,
    PublishLogsResponse,
)
from app.services.facebook_publish_service import publish_post, list_publish_logs

router = APIRouter(prefix="/publish", tags=["publish"])
logger = get_logger(__name__)


def _fb_permission_fix_hint() -> str:
    """Meta fix steps cho lỗi permission denied code=10/subcode=2069007."""
    return (
        "1) Trong Meta App: add Facebook Login product. "
        "2) Yêu cầu quyền pages_manage_posts, pages_read_engagement, pages_show_list. "
        "3) Generate user token hợp lệ rồi đổi sang page token qua /me/accounts. "
        "4) Đảm bảo user có Page task CREATE_CONTENT (hoặc quyền tương đương) trên Page. "
        "5) Cập nhật token vào env (FB_PAGE_ACCESS_TOKEN hoặc FACEBOOK_ACCESS_TOKEN) và restart service."
    )


@router.post("/facebook", response_model=PublishFacebookResponse)
async def post_publish_facebook(
    payload: PublishFacebookRequest,
    db: AsyncSession = Depends(get_db),
) -> PublishFacebookResponse:
    """
    Đăng một content đã approved lên Facebook Page (Graph API).
    Chỉ chấp nhận content_items.status == "approved".
    Ghi publish_log và audit (PUBLISH_REQUESTED, PUBLISH_SUCCESS / PUBLISH_FAIL).
    """
    try:
        log, error_message, error_details = await publish_post(
            db,
            tenant_id=payload.tenant_id,
            content_id=payload.content_id,
            actor="HUMAN",
            use_latest_asset=payload.use_latest_asset,
        )
    except ValueError as e:
        if str(e) == "facebook_not_configured":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Facebook chưa cấu hình (FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN).",
            )
        if str(e) == "content_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
        if str(e) == "content_not_approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ được đăng nội dung đã approved.",
            )
        raise
    if error_message == "media_required":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "media_required", "message": "Content yêu cầu ít nhất 1 ảnh/video (ready/cached). Gắn asset hoặc dùng use_latest_asset=true."},
        )
    if (
        error_details
        and error_details.get("code") == 10
        and error_details.get("subcode") == 2069007
    ):
        try:
            import structlog.contextvars

            correlation_id = structlog.contextvars.get_contextvars().get("correlation_id")
        except Exception:
            correlation_id = None
        logger.warning(
            "facebook_publish.permission_denied",
            tenant_id=str(payload.tenant_id),
            content_id=str(payload.content_id),
            details=error_details,
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "fb_permission_denied",
                "details": {
                    "code": error_details.get("code"),
                    "subcode": error_details.get("subcode"),
                    "message": error_details.get("message") or error_message,
                },
                "fix_hint": _fb_permission_fix_hint(),
            },
        )
    return PublishFacebookResponse(
        tenant_id=payload.tenant_id,
        content_id=payload.content_id,
        log_id=log.id,
        status=log.status,
        post_id=log.post_id,
        error_message=error_message or log.error_message,
    )


@router.get("/logs", response_model=PublishLogsResponse)
async def get_publish_logs(
    tenant_id: UUID = Query(..., description="Tenant UUID"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> PublishLogsResponse:
    """Lấy danh sách publish logs của tenant (mới nhất trước)."""
    logs = await list_publish_logs(db, tenant_id=tenant_id, limit=limit)
    return PublishLogsResponse(
        tenant_id=tenant_id,
        logs=[
            PublishLogOut(
                id=log.id,
                content_id=log.content_id,
                platform=log.platform,
                post_id=log.post_id,
                status=log.status,
                error_message=log.error_message,
                published_at=log.published_at,
                created_at=log.created_at,
            )
            for log in logs
        ],
    )
