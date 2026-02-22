"""Google Drive ingest + danh sách content assets."""
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import ContentAsset
from app.schemas.gdrive_assets import (
    AssetsListResponse,
    ContentAssetOut,
    GdriveIngestRequest,
    GdriveIngestResponse,
)
from app.services.gdrive_dropzone import ingest_ready_assets

router = APIRouter(prefix="/api", tags=["gdrive", "assets"])


@router.post("/gdrive/ingest", response_model=GdriveIngestResponse)
async def post_gdrive_ingest(
    payload: GdriveIngestRequest,
    db: AsyncSession = Depends(get_db),
) -> GdriveIngestResponse:
    """
    Quét thư mục READY (images/videos) trên Google Drive, tải về local, ghi content_assets.
    Trả về count_ingested, count_invalid.
    """
    try:
        count_ingested, count_invalid, count_skipped = await ingest_ready_assets(
            db, tenant_id=payload.tenant_id
        )
    except ValueError as e:
        err = str(e)
        if "GDRIVE_SA_JSON_PATH" in err or "GDRIVE_READY" in err or "GDRIVE_PROCESSED" in err or "GDRIVE_REJECTED" in err:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cấu hình Google Drive chưa đủ (GDRIVE_SA_JSON_PATH, folder IDs).",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
    return GdriveIngestResponse(
        tenant_id=payload.tenant_id,
        count_ingested=count_ingested,
        count_invalid=count_invalid,
        count_skipped=count_skipped,
    )


@router.get("/assets", response_model=AssetsListResponse)
async def get_assets(
    tenant_id: UUID = Query(..., description="Tenant UUID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Lọc theo status: ready|cached|invalid|uploaded"),
    db: AsyncSession = Depends(get_db),
) -> AssetsListResponse:
    """Lấy danh sách content assets của tenant, có thể lọc theo status."""
    q = select(ContentAsset).where(ContentAsset.tenant_id == tenant_id).order_by(ContentAsset.created_at.desc())
    if status_filter:
        q = q.where(ContentAsset.status == status_filter)
    r = await db.execute(q)
    assets = list(r.scalars().all())
    return AssetsListResponse(
        tenant_id=tenant_id,
        assets=[
            ContentAssetOut(
                id=a.id,
                tenant_id=a.tenant_id,
                content_id=a.content_id,
                asset_type=a.asset_type,
                drive_file_id=a.drive_file_id,
                file_name=a.file_name,
                mime_type=a.mime_type,
                size_bytes=a.size_bytes,
                storage_url=a.storage_url,
                local_path=a.local_path,
                status=a.status,
                fb_media_fbid=a.fb_media_fbid,
                fb_video_id=a.fb_video_id,
                error_reason=a.error_reason,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in assets
        ],
    )
