"""
Google Drive Dropzone: quét thư mục READY (images/videos), tải về local, ghi content_assets.
- Drive client dùng Service Account (GDRIVE_SA_JSON_PATH).
- validate_file: cho phép image/jpeg, image/png, image/webp, video/mp4, video/quicktime; giới hạn size theo ENV.
- ingest_ready_assets: scan folder READY → download → insert content_assets status=cached; invalid → move REJECTED, mark invalid.
"""
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models import ContentAsset

logger = get_logger(__name__)

# Mime types cho phép
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_MIMES = {"video/mp4", "video/quicktime"}
ALLOWED_MIMES = ALLOWED_IMAGE_MIMES | ALLOWED_VIDEO_MIMES

ASSET_TYPE_IMAGE = "image"
ASSET_TYPE_VIDEO = "video"
STATUS_READY = "ready"
STATUS_INVALID = "invalid"
STATUS_CACHED = "cached"
STATUS_UPLOADED = "uploaded"


def _get_drive_service():
    """
    Tạo Drive API client từ Service Account JSON.
    ENV: GDRIVE_SA_JSON_PATH (đường dẫn file JSON).
    """
    settings = get_settings()
    path = settings.gdrive_sa_json_path
    if not path or not os.path.isfile(path):
        raise ValueError("GDRIVE_SA_JSON_PATH không hợp lệ hoặc file không tồn tại")
    scopes = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",  # Cần để move file sang PROCESSED/REJECTED
    ]
    creds = service_account.Credentials.from_service_account_file(path, scopes=scopes)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_files(folder_id: str) -> List[Dict[str, Any]]:
    """
    Liệt kê file trong thư mục Drive (không đệ quy).
    Trả về list dict: id, name, mimeType, size (string từ API).
    """
    drive = _get_drive_service()
    q = f"'{folder_id}' in parents and trashed = false"
    results = (
        drive.files()
        .list(
            q=q,
            pageSize=100,
            fields="files(id, name, mimeType, size, parents)",
        )
        .execute()
    )
    return results.get("files", [])


def validate_file(meta: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Kiểm tra file có được phép ingest không (mime + size).
    Trả về (ok, asset_type, error_reason).
    asset_type: 'image' | 'video'. error_reason chỉ có khi ok=False.
    """
    settings = get_settings()
    mime = (meta.get("mimeType") or "").strip().lower()
    if mime not in ALLOWED_MIMES:
        return False, None, f"mime_type_not_allowed: {mime}"

    try:
        size_bytes = int(meta.get("size") or 0)
    except (TypeError, ValueError):
        return False, None, "invalid_size"

    if mime in ALLOWED_IMAGE_MIMES:
        asset_type = ASSET_TYPE_IMAGE
        max_bytes = settings.asset_max_image_mb * 1024 * 1024
    else:
        asset_type = ASSET_TYPE_VIDEO
        max_bytes = settings.asset_max_video_mb * 1024 * 1024

    if size_bytes > max_bytes:
        return False, asset_type, f"size_exceeds_limit:{asset_type}_{settings.asset_max_image_mb if asset_type == ASSET_TYPE_IMAGE else settings.asset_max_video_mb}MB"

    return True, asset_type, None


def download_file(file_id: str, dest_path: str) -> str:
    """
    Tải file Drive xuống dest_path (file path). Tạo thư mục cha nếu cần.
    Trả về đường dẫn local đã ghi (dest_path).
    """
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
    """
    Di chuyển file Drive sang thư mục target_folder_id.
    Cần quyền drive.file (service account phải có quyền trên file/folder).
    """
    drive = _get_drive_service()
    file_meta = drive.files().get(fileId=file_id, fields="parents").execute()
    previous_parents = ",".join(file_meta.get("parents", []))
    drive.files().update(
        fileId=file_id,
        addParents=target_folder_id,
        removeParents=previous_parents,
    ).execute()


def _storage_url(file_id: str) -> str:
    """Tạo storage_url dạng gdrive://{file_id}."""
    return f"gdrive://{file_id}"


async def ingest_ready_assets(db: AsyncSession, tenant_id: uuid.UUID) -> Tuple[int, int]:
    """
    Quét thư mục READY (images + videos), tải về LOCAL_MEDIA_DIR, insert content_assets.
    - Hợp lệ: download → insert status=cached, local_path set.
    - Không hợp lệ: move file sang REJECTED, insert (nếu cần) status=invalid, error_reason set; hoặc chỉ move và không insert.
    Theo spec: move invalid to REJECTED and mark invalid → insert row với status=invalid, error_reason.

    Trả về (count_ingested, count_invalid).
    """
    settings = get_settings()
    if not settings.gdrive_sa_json_path or not settings.gdrive_ready_images_folder_id:
        raise ValueError("GDRIVE_SA_JSON_PATH và GDRIVE_READY_IMAGES_FOLDER_ID bắt buộc")
    if not settings.gdrive_processed_folder_id or not settings.gdrive_rejected_folder_id:
        raise ValueError("GDRIVE_PROCESSED_FOLDER_ID và GDRIVE_REJECTED_FOLDER_ID bắt buộc")

    base_dir = Path(settings.local_media_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    tenant_dir = base_dir / str(tenant_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)

    count_ingested = 0
    count_invalid = 0
    ready_folders: List[Tuple[str, str]] = []  # (folder_id, asset_type)
    if settings.gdrive_ready_images_folder_id:
        ready_folders.append((settings.gdrive_ready_images_folder_id, ASSET_TYPE_IMAGE))
    if settings.gdrive_ready_videos_folder_id:
        ready_folders.append((settings.gdrive_ready_videos_folder_id, ASSET_TYPE_VIDEO))

    for folder_id, expected_type in ready_folders:
        try:
            files = list_files(folder_id)
        except Exception as e:
            logger.warning("gdrive_dropzone.list_files_failed", folder_id=folder_id, error=str(e))
            continue

        for meta in files:
            file_id = meta.get("id")
            if not file_id:
                continue
            name = meta.get("name") or "unknown"
            mime = meta.get("mimeType") or ""
            size_raw = meta.get("size")
            size_bytes = int(size_raw) if size_raw is not None else None

            ok, asset_type, error_reason = validate_file(meta)
            if not ok:
                count_invalid += 1
                try:
                    move_file(file_id, settings.gdrive_rejected_folder_id)
                except Exception as e:
                    logger.warning("gdrive_dropzone.move_rejected_failed", file_id=file_id, error=str(e))
                # Insert row invalid để audit
                asset = ContentAsset(
                    tenant_id=tenant_id,
                    content_id=None,
                    asset_type=asset_type or expected_type,
                    drive_file_id=file_id,
                    file_name=name,
                    mime_type=mime or None,
                    size_bytes=size_bytes,
                    storage_url=_storage_url(file_id),
                    local_path=None,
                    status=STATUS_INVALID,
                    error_reason=error_reason,
                )
                db.add(asset)
                await db.flush()
                continue

            # Hợp lệ: download rồi insert cached
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
                    logger.warning("gdrive_dropzone.move_rejected_after_download_failed", file_id=file_id, error=str(e2))
                asset = ContentAsset(
                    tenant_id=tenant_id,
                    content_id=None,
                    asset_type=asset_type,
                    drive_file_id=file_id,
                    file_name=name,
                    mime_type=mime or None,
                    size_bytes=size_bytes,
                    storage_url=_storage_url(file_id),
                    local_path=None,
                    status=STATUS_INVALID,
                    error_reason=f"download_failed:{e}",
                )
                db.add(asset)
                await db.flush()
                continue

            asset = ContentAsset(
                tenant_id=tenant_id,
                content_id=None,
                asset_type=asset_type,
                drive_file_id=file_id,
                file_name=name,
                mime_type=mime or None,
                size_bytes=size_bytes,
                storage_url=_storage_url(file_id),
                local_path=str(dest_path),
                status=STATUS_CACHED,
            )
            db.add(asset)
            await db.flush()
            count_ingested += 1
            logger.info("gdrive_dropzone.ingested", file_id=file_id, asset_type=asset_type, tenant_id=str(tenant_id))

    return count_ingested, count_invalid
