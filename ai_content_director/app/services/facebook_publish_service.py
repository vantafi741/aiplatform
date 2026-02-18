"""
Đăng bài đã APPROVED lên Facebook Page qua Graph API.
- Nếu content.require_media=true mà không có asset phù hợp → fail với lỗi rõ (media_required).
- use_latest_asset=true: lấy asset READY mới nhất chưa gắn content.
- Ảnh: /photos published=false, rồi /feed với attached_media. Video: /videos.
- Thành công: update asset status PROCESSED + move file Drive sang PROCESSED.
- Thất bại: asset status REJECTED + move Drive sang REJECTED + error_reason.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models import ContentAsset, ContentItem, PublishLog
from app.services.approval_service import log_audit_event
from app.services.gdrive_dropzone import move_file

logger = get_logger(__name__)

PLATFORM_FACEBOOK = "facebook"
GRAPH_BASE = "https://graph.facebook.com"
HTTP_TIMEOUT = 30.0
VIDEO_UPLOAD_TIMEOUT = 300.0
MAX_RETRIES = 2

STATUS_READY = "READY"
STATUS_PROCESSED = "PROCESSED"
STATUS_REJECTED = "REJECTED"


async def _get_asset_for_publish(
    db: AsyncSession,
    tenant_id: UUID,
    content_id: UUID,
    use_latest_asset: bool,
) -> Optional[ContentAsset]:
    """
    Lấy 1 asset READY: ưu tiên asset gắn content_id; nếu use_latest_asset lấy asset READY chưa gắn content (mới nhất).
    """
    q = (
        select(ContentAsset)
        .where(
            ContentAsset.tenant_id == tenant_id,
            ContentAsset.content_id == content_id,
            ContentAsset.status == STATUS_READY,
        )
        .order_by(ContentAsset.created_at.desc())
        .limit(1)
    )
    r = await db.execute(q)
    asset = r.scalar_one_or_none()
    if asset:
        return asset
    if not use_latest_asset:
        return None
    q2 = (
        select(ContentAsset)
        .where(
            ContentAsset.tenant_id == tenant_id,
            ContentAsset.content_id.is_(None),
            ContentAsset.status == STATUS_READY,
        )
        .order_by(ContentAsset.created_at.desc())
        .limit(1)
    )
    r2 = await db.execute(q2)
    return r2.scalar_one_or_none()


def _move_asset_drive(asset: ContentAsset, to_processed: bool) -> None:
    """Move file Drive sang PROCESSED hoặc REJECTED."""
    settings = get_settings()
    if to_processed and settings.gdrive_processed_folder_id:
        try:
            move_file(asset.drive_file_id, settings.gdrive_processed_folder_id)
        except Exception as e:
            logger.warning("facebook_publish.move_processed_failed", asset_id=str(asset.id), error=str(e))
    elif not to_processed and settings.gdrive_rejected_folder_id:
        try:
            move_file(asset.drive_file_id, settings.gdrive_rejected_folder_id)
        except Exception as e:
            logger.warning("facebook_publish.move_rejected_failed", asset_id=str(asset.id), error=str(e))


async def publish_post(
    db: AsyncSession,
    tenant_id: UUID,
    content_id: UUID,
    actor: str = "HUMAN",
    use_latest_asset: bool = False,
) -> Tuple[PublishLog, Optional[str]]:
    """
    Đăng content_item lên Facebook. require_media=true thì bắt buộc có asset READY; không có → error_message="media_required".
    Thành công: asset status PROCESSED + move Drive PROCESSED. Thất bại: asset REJECTED + move REJECTED + error_reason.
    """
    settings = get_settings()
    if not settings.facebook_page_id or not settings.facebook_access_token:
        raise ValueError("facebook_not_configured")

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

    message = (item.caption or "").strip() or item.title
    if item.hashtags:
        message = f"{message}\n\n{item.hashtags}".strip()

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

    asset: Optional[ContentAsset] = None
    require_media = getattr(item, "require_media", False)
    if require_media:
        asset = await _get_asset_for_publish(db, tenant_id, content_id, use_latest_asset)
        if not asset:
            log.status = "fail"
            log.error_message = "media_required"
            log.published_at = None
            await db.flush()
            await log_audit_event(
                db,
                tenant_id=tenant_id,
                content_id=content_id,
                event_type="PUBLISH_FAIL",
                actor=actor,
                metadata_={"platform": PLATFORM_FACEBOOK, "error": "media_required"},
            )
            logger.warning("facebook_publish.media_required", content_id=str(content_id))
            return log, "media_required"

    last_error: Optional[str] = None
    http_status: Optional[int] = None
    post_id: Optional[str] = None

    if asset:
        if asset.asset_type == "video":
            post_id, last_error, http_status = await _publish_video(
                settings.facebook_page_id,
                settings.facebook_access_token,
                settings.facebook_api_version,
                asset,
                message,
            )
        else:
            post_id, last_error, http_status = await _publish_photo(
                settings.facebook_page_id,
                settings.facebook_access_token,
                settings.facebook_api_version,
                asset,
                message,
            )

        if last_error:
            asset.status = STATUS_REJECTED
            asset.error_reason = last_error
            _move_asset_drive(asset, to_processed=False)
            await db.flush()
        else:
            asset.status = STATUS_PROCESSED
            asset.error_reason = None
            if asset.content_id is None:
                asset.content_id = content_id
            _move_asset_drive(asset, to_processed=True)
            await db.flush()
    else:
        url = f"{GRAPH_BASE}/{settings.facebook_api_version}/{settings.facebook_page_id}/feed"
        payload = {"message": message, "access_token": settings.facebook_access_token}
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                    resp = await client.post(url, data=payload)
                http_status = resp.status_code
                if resp.status_code == 200:
                    data = resp.json()
                    post_id = data.get("id") or data.get("post_id") or (str(data["id"]) if "id" in data else None)
                    break
                try:
                    err_body = resp.json()
                    last_error = err_body.get("error", {}).get("message", resp.text) or resp.text
                except Exception:
                    last_error = resp.text or f"HTTP {resp.status_code}"
            except httpx.TimeoutException as e:
                last_error = f"Timeout: {e}"
                http_status = None
            except httpx.RequestError as e:
                last_error = str(e)
                resp_obj = getattr(e, "response", None)
                http_status = resp_obj.status_code if resp_obj is not None else None
            if attempt < MAX_RETRIES:
                logger.warning("facebook_publish.retry", attempt=attempt + 1, error=last_error)

    if last_error or not post_id:
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
            metadata_={"platform": PLATFORM_FACEBOOK, "http_status": http_status, "error": last_error},
        )
        logger.warning("facebook_publish.fail", content_id=str(content_id), error=last_error)
        return log, last_error

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
        metadata_={"platform": PLATFORM_FACEBOOK, "post_id": post_id, "http_status": http_status or 200},
    )
    logger.info("facebook_publish.success", content_id=str(content_id), post_id=post_id)
    return log, None


async def _publish_photo(
    page_id: str,
    access_token: str,
    api_version: str,
    asset: ContentAsset,
    message: str,
) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Upload ảnh published=false, rồi /feed với attached_media. Trả về (post_id, error, http_status)."""
    local_path = asset.local_path
    if not local_path or not Path(local_path).is_file():
        return None, "asset_local_file_missing", None

    url = f"{GRAPH_BASE}/{api_version}/{page_id}/photos"
    data = {"access_token": access_token, "published": "false"}
    try:
        with open(local_path, "rb") as f:
            files = {"source": (asset.file_name or "image", f, asset.mime_type or "image/jpeg")}
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.post(url, data=data, files=files)
        if resp.status_code != 200:
            try:
                err_body = resp.json()
                err_msg = err_body.get("error", {}).get("message", resp.text) or resp.text
            except Exception:
                err_msg = resp.text or f"HTTP {resp.status_code}"
            return None, err_msg, resp.status_code
        data_res = resp.json()
        photo_id = data_res.get("id") or data_res.get("post_id") or (str(data_res["id"]) if "id" in data_res else None)
        if not photo_id:
            return None, "photo_upload_no_id", resp.status_code

        feed_url = f"{GRAPH_BASE}/{api_version}/{page_id}/feed"
        feed_payload = {
            "message": message,
            "access_token": access_token,
            "attached_media": [{"media_fbid": photo_id}],
        }
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            feed_resp = await client.post(feed_url, data=feed_payload)
        if feed_resp.status_code != 200:
            try:
                err_body = feed_resp.json()
                err_msg = err_body.get("error", {}).get("message", feed_resp.text) or feed_resp.text
            except Exception:
                err_msg = feed_resp.text or f"HTTP {feed_resp.status_code}"
            return None, err_msg, feed_resp.status_code
        feed_data = feed_resp.json()
        post_id = feed_data.get("id") or feed_data.get("post_id") or (str(feed_data["id"]) if "id" in feed_data else None)
        return post_id, None, feed_resp.status_code
    except httpx.TimeoutException as e:
        return None, f"Timeout: {e}", None
    except httpx.RequestError as e:
        return None, str(e), getattr(getattr(e, "response", None), "status_code", None)
    except Exception as e:
        return None, str(e), None


async def _publish_video(
    page_id: str,
    access_token: str,
    api_version: str,
    asset: ContentAsset,
    message: str,
) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Upload video /videos với description. Trả về (post_id, error, http_status)."""
    local_path = asset.local_path
    if not local_path or not Path(local_path).is_file():
        return None, "asset_local_file_missing", None

    url = f"{GRAPH_BASE}/{api_version}/{page_id}/videos"
    data = {"access_token": access_token, "description": message}
    try:
        with open(local_path, "rb") as f:
            files = {"source": (asset.file_name or "video", f, asset.mime_type or "video/mp4")}
            async with httpx.AsyncClient(timeout=VIDEO_UPLOAD_TIMEOUT) as client:
                resp = await client.post(url, data=data, files=files)
        if resp.status_code != 200:
            try:
                err_body = resp.json()
                err_msg = err_body.get("error", {}).get("message", resp.text) or resp.text
            except Exception:
                err_msg = resp.text or f"HTTP {resp.status_code}"
            return None, err_msg, resp.status_code
        data_res = resp.json()
        post_id = data_res.get("post_id") or data_res.get("id") or (str(data_res["id"]) if "id" in data_res else None)
        return post_id, None, resp.status_code
    except httpx.TimeoutException as e:
        return None, f"Timeout: {e}", None
    except httpx.RequestError as e:
        return None, str(e), getattr(getattr(e, "response", None), "status_code", None)
    except Exception as e:
        return None, str(e), None


async def list_publish_logs(
    db: AsyncSession,
    tenant_id: UUID,
    limit: int = 50,
) -> list[PublishLog]:
    """Lấy danh sách publish logs của tenant, mới nhất trước."""
    q = (
        select(PublishLog)
        .join(ContentItem, ContentItem.id == PublishLog.content_id)
        .where(ContentItem.tenant_id == tenant_id)
        .order_by(PublishLog.created_at.desc())
        .limit(limit)
    )
    r = await db.execute(q)
    return list(r.scalars().all())
