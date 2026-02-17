"""KB (Knowledge Base) API: items CRUD + query ILIKE."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.kb import (
    KbItemCreate,
    KbItemOut,
    KbBulkRequest,
    KbBulkResponse,
    KbQueryRequest,
    KbQueryResponse,
    KbQueryItem,
)
from app.services.kb_service import (
    create_kb_item,
    bulk_create_kb_items,
    list_kb_items,
    query_kb_ilike,
)

router = APIRouter(prefix="/kb", tags=["kb"])


@router.post("/items", response_model=KbItemOut, status_code=status.HTTP_201_CREATED)
async def post_kb_item(
    payload: KbItemCreate,
    db: AsyncSession = Depends(get_db),
) -> KbItemOut:
    """Tạo một mục KB (FAQ / ngữ cảnh)."""
    item = await create_kb_item(
        db,
        tenant_id=payload.tenant_id,
        title=payload.title,
        content=payload.content,
        tags=payload.tags or None,
    )
    return KbItemOut.model_validate(item)


@router.post("/items/bulk", response_model=KbBulkResponse, status_code=status.HTTP_201_CREATED)
async def post_kb_bulk(
    payload: KbBulkRequest,
    db: AsyncSession = Depends(get_db),
) -> KbBulkResponse:
    """Bulk ingest nhiều mục KB."""
    items = [{"title": i.title, "content": i.content, "tags": i.tags} for i in payload.items]
    ids = await bulk_create_kb_items(db, tenant_id=payload.tenant_id, items=items)
    return KbBulkResponse(tenant_id=payload.tenant_id, created=len(ids), ids=ids)


@router.get("/items", response_model=list[KbItemOut])
async def get_kb_items(
    tenant_id: UUID = Query(..., description="Tenant UUID"),
    db: AsyncSession = Depends(get_db),
) -> list[KbItemOut]:
    """Lấy tất cả KB items của tenant."""
    items = await list_kb_items(db, tenant_id=tenant_id)
    return [KbItemOut.model_validate(i) for i in items]


@router.post("/query", response_model=KbQueryResponse)
async def post_kb_query(
    payload: KbQueryRequest,
    db: AsyncSession = Depends(get_db),
) -> KbQueryResponse:
    """Tìm KB theo query (ILIKE trên title + content), trả về top N."""
    items = await query_kb_ilike(
        db,
        tenant_id=payload.tenant_id,
        query=payload.query,
        top_k=payload.top_k,
    )
    return KbQueryResponse(
        tenant_id=payload.tenant_id,
        query=payload.query,
        items=[
            KbQueryItem(id=i.id, title=i.title, content=i.content, tags=i.tags)
            for i in items
        ],
        total=len(items),
    )
