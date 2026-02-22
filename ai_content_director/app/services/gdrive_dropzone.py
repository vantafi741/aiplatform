"""
Google Drive Dropzone: quet thu muc READY (images/videos), tai ve local, ghi content_assets.
Idempotent ingest:
- Query (tenant_id, drive_file_id) truoc khi download.
- Neu da ton tai va local file hop le -> skip (khong download lai).
- Neu row cu invalid/download_failed hoac local file hu -> retry download va update row cu.
"""

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ContentAsset

logger = logging.getLogger(__name__)

# Mime types cho phep
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_MIMES = {"video/mp4", "video/quicktime"}
ALLOWED_MIMES = ALLOWED_IMAGE_MIMES | ALLOWED_VIDEO_MIMES

ASSET_TYPE_IMAGE = "image"
ASSET_TYPE_VIDEO = "video"
STATUS_INVALID = "invalid"
STATUS_CACHED = "cached"


def _get_drive_service():
    """Tao Drive API client tu Service Account JSON."""
    settings = get_settings()
    path = settings.gdrive_sa_json_path
    if not path or not os.path.isfile(path):
        raise ValueError("GDRIVE_SA_JSON_PATH khong hop le hoac file khong ton tai")
    scopes = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = service_account.Credentials.from_service_account_file(path, scopes=scopes)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_files(folder_id: str) -> List[Dict[str, Any]]:
    """Liet ke file trong thu muc Drive (khong de quy)."""
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
    Kiem tra file co duoc phep ingest khong (mime + size).
    Tra ve (ok, asset_type, error_reason).
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
        max_mb = settings.asset_max_image_mb if asset_type == ASSET_TYPE_IMAGE else settings.asset_max_video_mb
        return False, asset_type, f"size_exceeds_limit:{asset_type}_{max_mb}MB"

    return True, asset_type, None


def download_file(file_id: str, dest_path: str) -> str:
    """Tai file Drive xuong dest_path."""
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
    """Di chuyen file Drive sang thu muc target_folder_id."""
    drive = _get_drive_service()
    file_meta = drive.files().get(fileId=file_id, fields="parents").execute()
    previous_parents = ",".join(file_meta.get("parents", []))
    drive.files().update(
        fileId=file_id,
        addParents=target_folder_id,
        removeParents=previous_parents,
    ).execute()


def _storage_url(file_id: str) -> str:
    """Tao storage_url dang gdrive://{file_id}."""
    return f"gdrive://{file_id}"


async def _get_existing_asset(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    drive_file_id: str,
) -> Optional[ContentAsset]:
    """Lay 1 asset theo (tenant_id, drive_file_id)."""
    q = (
        select(ContentAsset)
        .where(
            ContentAsset.tenant_id == tenant_id,
            ContentAsset.drive_file_id == drive_file_id,
        )
        .limit(1)
    )
    r = await db.execute(q)
    return r.scalar_one_or_none()


def _is_failed_status(existing: ContentAsset) -> bool:
    """True neu row dang invalid hoac co dau hieu download_failed."""
    if existing.status == STATUS_INVALID:
        return True
    if existing.error_reason and existing.error_reason.lower().startswith("download_failed"):
        return True
    return False


def _is_local_file_valid(existing: ContentAsset) -> bool:
    """
    Local file hop le khi:
    - local_path ton tai tren disk
    - file size > 0
    - neu size_bytes cua row co gia tri thi phai match
    """
    if not existing.local_path:
        return False
    if not os.path.isfile(existing.local_path):
        return False
    actual_size = os.path.getsize(existing.local_path)
    if actual_size <= 0:
        return False
    if existing.size_bytes is not None and existing.size_bytes > 0 and actual_size != existing.size_bytes:
        return False
    return True


def _is_unique_violation(err: IntegrityError) -> bool:
    """Nhan dien unique violation cho ux_content_assets_tenant_drive_file."""
    msg = str(getattr(err, "orig", err))
    return (
        "ux_content_assets_tenant_drive_file" in msg
        or "content_assets_tenant_id_drive_file_id" in msg
        or "duplicate key value violates unique constraint" in msg
    )


async def _flush_with_duplicate_guard(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    drive_file_id: str,
) -> bool:
    """
    Flush an toan cho duplicate UNIQUE (tenant_id, drive_file_id).
    Return True neu flush thanh cong, False neu duplicate (da rollback).
    """
    try:
        await db.flush()
        return True
    except IntegrityError as err:
        if _is_unique_violation(err):
            await db.rollback()
            logger.info(
                "gdrive_dropzone.skip_duplicate tenant_id=%s drive_file_id=%s",
                tenant_id,
                drive_file_id,
            )
            return False
        raise


async def ingest_ready_assets(db: AsyncSession, tenant_id: uuid.UUID) -> Tuple[int, int, int]:
    """
    Quet READY folders, ingest idempotent.

    Return:
    - count_ingested: so row moi cached + so row retry thanh cong ve cached
    - count_invalid: so file invalid
    - count_skipped: so file skip do duplicate/existing
    """
    settings = get_settings()
    if not settings.gdrive_sa_json_path or not settings.gdrive_ready_images_folder_id:
        raise ValueError("GDRIVE_SA_JSON_PATH va GDRIVE_READY_IMAGES_FOLDER_ID bat buoc")
    if not settings.gdrive_processed_folder_id or not settings.gdrive_rejected_folder_id:
        raise ValueError("GDRIVE_PROCESSED_FOLDER_ID va GDRIVE_REJECTED_FOLDER_ID bat buoc")

    base_dir = Path(settings.local_media_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    tenant_dir = base_dir / str(tenant_id)
    tenant_dir.mkdir(parents=True, exist_ok=True)

    count_ingested = 0
    count_invalid = 0
    count_skipped = 0

    ready_folders: List[Tuple[str, str]] = []
    if settings.gdrive_ready_images_folder_id:
        ready_folders.append((settings.gdrive_ready_images_folder_id, ASSET_TYPE_IMAGE))
    if settings.gdrive_ready_videos_folder_id:
        ready_folders.append((settings.gdrive_ready_videos_folder_id, ASSET_TYPE_VIDEO))

    for folder_id, expected_type in ready_folders:
        try:
            files = list_files(folder_id)
        except Exception as e:
            logger.warning("gdrive_dropzone.list_files_failed folder_id=%s error=%s", folder_id, e)
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

            safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)[:200]
            local_name = f"{file_id}_{safe_name}"
            default_dest_path = tenant_dir / local_name

            existing = await _get_existing_asset(db, tenant_id, file_id)
            if existing is not None:
                local_valid = _is_local_file_valid(existing)
                failed_status = _is_failed_status(existing)

                # Skip: row da co + local file hop le + khong phai failed status
                if local_valid and not failed_status:
                    count_skipped += 1
                    logger.info(
                        "gdrive_dropzone.skip_existing tenant_id=%s drive_file_id=%s",
                        tenant_id,
                        file_id,
                    )
                    continue

                # Retry: file local thieu/0 bytes, hoac status failed
                reason = "failed_status" if failed_status else "local_missing_or_invalid"
                logger.info(
                    "gdrive_dropzone.retry_existing tenant_id=%s drive_file_id=%s reason=%s",
                    tenant_id,
                    file_id,
                    reason,
                )

                # Neu file khong hop le theo policy hien tai -> giu invalid va bo qua
                if not ok:
                    existing.status = STATUS_INVALID
                    existing.error_reason = error_reason
                    existing.file_name = name
                    existing.mime_type = mime or None
                    existing.size_bytes = size_bytes
                    existing.storage_url = _storage_url(file_id)
                    db.add(existing)
                    inserted = await _flush_with_duplicate_guard(
                        db,
                        tenant_id=tenant_id,
                        drive_file_id=file_id,
                    )
                    if inserted:
                        count_invalid += 1
                    else:
                        count_skipped += 1
                    continue

                # Retry download vao cung target path neu co, fallback theo ten mac dinh
                retry_dest = existing.local_path or str(default_dest_path)
                try:
                    download_file(file_id, retry_dest)
                    existing.file_name = name
                    existing.mime_type = mime or None
                    existing.size_bytes = size_bytes
                    existing.local_path = retry_dest
                    existing.storage_url = _storage_url(file_id)
                    existing.status = STATUS_CACHED
                    existing.error_reason = None
                    if asset_type:
                        existing.asset_type = asset_type
                    db.add(existing)
                    inserted = await _flush_with_duplicate_guard(
                        db,
                        tenant_id=tenant_id,
                        drive_file_id=file_id,
                    )
                    if inserted:
                        count_ingested += 1
                    else:
                        count_skipped += 1
                except Exception as e:
                    existing.status = STATUS_INVALID
                    existing.error_reason = f"download_failed:{e}"
                    existing.storage_url = _storage_url(file_id)
                    db.add(existing)
                    inserted = await _flush_with_duplicate_guard(
                        db,
                        tenant_id=tenant_id,
                        drive_file_id=file_id,
                    )
                    if inserted:
                        count_invalid += 1
                    else:
                        count_skipped += 1
                continue

            # Chua ton tai -> xu ly moi
            if not ok:
                count_invalid += 1
                try:
                    move_file(file_id, settings.gdrive_rejected_folder_id)
                except Exception as e:
                    logger.warning("gdrive_dropzone.move_rejected_failed file_id=%s error=%s", file_id, e)

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
                inserted = await _flush_with_duplicate_guard(
                    db,
                    tenant_id=tenant_id,
                    drive_file_id=file_id,
                )
                if not inserted:
                    count_skipped += 1
                    continue
                continue

            # File moi hop le -> download + insert cached
            try:
                download_file(file_id, str(default_dest_path))
            except Exception as e:
                count_invalid += 1
                try:
                    move_file(file_id, settings.gdrive_rejected_folder_id)
                except Exception as e2:
                    logger.warning(
                        "gdrive_dropzone.move_rejected_after_download_failed file_id=%s error=%s",
                        file_id,
                        e2,
                    )

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
                inserted = await _flush_with_duplicate_guard(
                    db,
                    tenant_id=tenant_id,
                    drive_file_id=file_id,
                )
                if not inserted:
                    count_skipped += 1
                    continue
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
                local_path=str(default_dest_path),
                status=STATUS_CACHED,
                error_reason=None,
            )
            db.add(asset)
            inserted = await _flush_with_duplicate_guard(
                db,
                tenant_id=tenant_id,
                drive_file_id=file_id,
            )
            if inserted:
                count_ingested += 1
                logger.info(
                    "gdrive_dropzone.ingested tenant_id=%s drive_file_id=%s",
                    tenant_id,
                    file_id,
                )
            else:
                count_skipped += 1
                continue

    logger.info(
        "gdrive_dropzone.ingest_done tenant_id=%s count_ingested=%s count_invalid=%s count_skipped=%s",
        tenant_id,
        count_ingested,
        count_invalid,
        count_skipped,
    )
    return count_ingested, count_invalid, count_skipped
