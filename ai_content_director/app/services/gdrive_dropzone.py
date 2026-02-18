"""
Google Drive Dropzone: quét folder READY (images/videos), validate mime/size, tải về LOCAL_MEDIA_DIR,
tạo record content_assets. File invalid → move REJECTED (Drive) + lưu error_reason.
"""
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models import ContentAsset

logger = get_logger(__name__)

STATUS_READY = "READY"
STATUS_PROCESSED = "PROCESSED"
STATUS_REJECTED = "REJECTED"
ASSET_TYPE_IMAGE = "image"
ASSET_TYPE_VIDEO = "video"


def _parse_mime_list(csv: str) -> set[str]:
    """Chuyển chuỗi mime comma-separated thành set (lowercase, strip)."""
    return {s.strip().lower() for s in (csv or "").split(",") if s.strip()}


def _get_drive_service():
    """Tạo Drive API client từ Service Account JSON. ENV: GDRIVE_SA_KEY_PATH."""
    settings = get_settings()
    path = settings.gdrive_sa_key_path
    if not path or not os.path.isfile(path):
        raise ValueError("GDRIVE_SA_KEY_PATH không hợp lệ hoặc file không tồn tại")
    scopes = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = service_account.Credentials.from_service_account_file(path, scopes=scopes)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_files(folder_id: str) -> List[Dict[str, Any]]:
    """Liệt kê file trong thư mục Drive (không đệ quy)."""
    drive = _get_drive_service()
    q = f"'{folder_id}' in parents and trashed = false"
    results = (
        drive.files()
        .list(q=q, pageSize=100, fields="files(id, name, mimeType, size, parents)")
        .execute()
    )
    return results.get("files", [])


def validate_file(meta: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Kiểm tra file theo mime (ASSET_ALLOWED_MIME_IMAGE / ASSET_ALLOWED_MIME_VIDEO) và size (ASSET_MAX_SIZE_MB).
    Trả về (ok, asset_type, error_reason). asset_type: image | video.
    """
    settings = get_settings()
    mime = (meta.get("mimeType") or "").strip().lower()
    allowed_image = _parse_mime_list(settings.asset_allowed_mime_image)
    allowed_video = _parse_mime_list(settings.asset_allowed_mime_video)

    if mime in allowed_image:
        asset_type = ASSET_TYPE_IMAGE
    elif mime in allowed_video:
        asset_type = ASSET_TYPE_VIDEO
    else:
        return False, None, f"mime_not_allowed:{mime}"

    try:
        size_bytes = int(meta.get("size") or 0)
    except (TypeError, ValueError):
        return False, asset_type, "invalid_size"

    max_bytes = settings.asset_max_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        return False, asset_type, f"size_exceeds_limit:{settings.asset_max_size_mb}MB"

    return True, asset_type, None


def download_file(file_id: str, dest_path: str) -> str:
    """Tải file Drive xuống dest_path. Trả về đường dẫn local."""
    drive = _get_drive_service()
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    request = drive.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return dest_path


def move_file(file_id: str, target_folder_id: str) -> None:
    """Di chuyển file Drive sang target_folder_id."""
    drive = _get_drive_service()
    file_meta = drive.files().get(fileId=file_id, fields="parents").execute()
    previous_parents = ",".join(file_meta.get("parents", []))
    drive.files().update(
        fileId=file_id,
        addParents=target_folder_id,
        removeParents=previous_parents,
    ).execute()
    logger.info("gdrive_dropzone.move_file", file_id=file_id, target_folder_id=target_folder_id)


async def ingest_ready_assets(db: AsyncSession, tenant_id: uuid.UUID) -> Tuple[int, int]:
    """
    Quét folder READY, validate, tải về LOCAL_MEDIA_DIR, tạo content_assets.
    Hợp lệ: status READY, local_path set. Không hợp lệ: move Drive sang REJECTED, record status REJECTED + error_reason.
    Trả về (count_ingested, count_invalid).
    """
    settings = get_settings()
    if not settings.gdrive_sa_key_path or not settings.gdrive_ready_folder_id:
        raise ValueError("GDRIVE_SA_KEY_PATH và GDRIVE_READY_FOLDER_ID bắt buộc")
    if not settings.gdrive_processed_folder_id or not settings.gdrive_rejected_folder_id:
        raise ValueError("GDRIVE_PROCESSED_FOLDER_ID và GDRIVE_REJECTED_FOLDER_ID bắt buộc")

    base_dir = Path(settings.local_media_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    tenant_dir = base_dir / str(tenant_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)

    count_ingested = 0
    count_invalid = 0
    folder_id = settings.gdrive_ready_folder_id

    try:
        files = list_files(folder_id)
    except Exception as e:
        logger.warning("gdrive_dropzone.list_files_failed", folder_id=folder_id, error=str(e))
        return 0, 0

    for meta in files:
        file_id = meta.get("id")
        if not file_id:
            continue
        name = meta.get("name") or "unknown"
        mime = meta.get("mimeType") or ""
        size_raw = meta.get("size")
        size_bytes = int(size_raw) if size_raw is not None else None
        parents = meta.get("parents") or []
        drive_parent_folder = parents[0] if parents else None

        ok, asset_type, error_reason = validate_file(meta)
        if not ok:
            count_invalid += 1
            try:
                move_file(file_id, settings.gdrive_rejected_folder_id)
            except Exception as e:
                logger.warning("gdrive_dropzone.move_rejected_failed", file_id=file_id, error=str(e))
            asset = ContentAsset(
                tenant_id=tenant_id,
                content_id=None,
                drive_file_id=file_id,
                drive_parent_folder=drive_parent_folder,
                file_name=name,
                mime_type=mime or None,
                size_bytes=size_bytes,
                asset_type=asset_type or ASSET_TYPE_IMAGE,
                local_path=None,
                status=STATUS_REJECTED,
                error_reason=error_reason,
            )
            db.add(asset)
            await db.flush()
            logger.info("gdrive_dropzone.invalid", file_id=file_id, error_reason=error_reason)
            continue

        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)[:200]
        local_name = f"{file_id}_{safe_name}"
        dest_path = tenant_dir / local_name
        try:
            download_file(file_id, str(dest_path))
        except Exception as e:
            count_invalid += 1
            try:
                move_file(file_id, settings.gdrive_rejected_folder_id)
            except Exception as e2:
                logger.warning("gdrive_dropzone.move_after_download_fail", file_id=file_id, error=str(e2))
            asset = ContentAsset(
                tenant_id=tenant_id,
                content_id=None,
                drive_file_id=file_id,
                drive_parent_folder=drive_parent_folder,
                file_name=name,
                mime_type=mime or None,
                size_bytes=size_bytes,
                asset_type=asset_type,
                local_path=None,
                status=STATUS_REJECTED,
                error_reason=f"download_failed:{e}",
            )
            db.add(asset)
            await db.flush()
            continue

        asset = ContentAsset(
            tenant_id=tenant_id,
            content_id=None,
            drive_file_id=file_id,
            drive_parent_folder=drive_parent_folder,
            file_name=name,
            mime_type=mime or None,
            size_bytes=size_bytes,
            asset_type=asset_type,
            local_path=str(dest_path),
            status=STATUS_READY,
        )
        db.add(asset)
        await db.flush()
        count_ingested += 1
        logger.info("gdrive_dropzone.ingested", file_id=file_id, asset_type=asset_type, tenant_id=str(tenant_id))

    return count_ingested, count_invalid
