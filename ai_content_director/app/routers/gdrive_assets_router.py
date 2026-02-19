"""Google Drive ingest + danh sách content assets."""
from uuid import UUID
from typing import Optional
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
    Quét folder READY trên Google Drive, validate mime/size, tải về LOCAL_MEDIA_DIR, tạo content_assets.
    Trả về count_ingested, count_invalid.
    """
    try:
        count_ingested, count_invalid = await ingest_ready_assets(db, tenant_id=payload.tenant_id)
    except ValueError as e:
        err = str(e)
        if "GDRIVE_SA_KEY_PATH" in err or "GDRIVE_READY" in err or "GDRIVE_PROCESSED" in err or "GDRIVE_REJECTED" in err:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cấu hình Google Drive chưa đủ (GDRIVE_SA_KEY_PATH, folder IDs).",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
    return GdriveIngestResponse(
        tenant_id=payload.tenant_id,
        count_ingested=count_ingested,
        count_invalid=count_invalid,
    )


@router.get("/assets", response_model=AssetsListResponse)
async def get_assets(
    tenant_id: UUID = Query(..., description="Tenant UUID"),
    status_filter: Optional[str] = Query(None, alias="status", description="READY | PROCESSED | REJECTED"),
    content_id: Optional[UUID] = Query(None, description="Lọc theo content_id"),
    db: AsyncSession = Depends(get_db),
) -> AssetsListResponse:
    """Lấy danh sách content assets, optional filters: tenant_id, status, content_id."""
    q = select(ContentAsset).where(ContentAsset.tenant_id == tenant_id).order_by(ContentAsset.created_at.desc())
    if status_filter:
        q = q.where(ContentAsset.status == status_filter)
    if content_id is not None:
        q = q.where(ContentAsset.content_id == content_id)
    r = await db.execute(q)
    assets = list(r.scalars().all())
    return AssetsListResponse(
        tenant_id=tenant_id,
        assets=[
            ContentAssetOut(
                id=a.id,
                tenant_id=a.tenant_id,
                content_id=a.content_id,
                drive_file_id=a.drive_file_id,
                drive_parent_folder=a.drive_parent_folder,
                file_name=a.file_name,
                mime_type=a.mime_type,
                size_bytes=a.size_bytes,
                asset_type=a.asset_type,
                local_path=a.local_path,
                status=a.status,
                error_reason=a.error_reason,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in assets
        ],
    )
