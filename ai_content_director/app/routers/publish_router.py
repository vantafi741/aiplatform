"""Publish lên Facebook (Graph API) + xem publish logs."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.publish import (
    PublishFacebookRequest,
    PublishFacebookResponse,
    PublishLogOut,
    PublishLogsResponse,
)
from app.services.facebook_publish_service import publish_post, list_publish_logs

router = APIRouter(prefix="/publish", tags=["publish"])


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
        log, error_message = await publish_post(
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
            detail={
                "code": "media_required",
                "message": "Content yêu cầu ít nhất 1 asset (READY). Gắn asset hoặc dùng use_latest_asset=true.",
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
