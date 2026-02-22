"""Revenue MVP Module 2: Content Generator endpoints."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.revenue_mv2 import (
    ContentGenerateRequest,
    ContentGenerateResponse,
    ContentItemOut,
)
from app.services.content_service_mv2 import (
    generate_content,
    get_content_by_id,
    get_content_by_plan_id,
)

router = APIRouter(prefix="/api", tags=["revenue_mv2"])


@router.post(
    "/content/generate",
    response_model=ContentGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_content_generate(
    payload: ContentGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> ContentGenerateResponse:
    """
    Generate one content item for (tenant_id, plan_id, day).
    Day 1..30. Logs usage. Fallback template if no OpenAI key or error.
    """
    try:
        item = await generate_content(
            db,
            tenant_id=payload.tenant_id,
            plan_id=payload.plan_id,
            day=payload.day,
            asset_id=payload.asset_id,
        )
        return ContentGenerateResponse(content=ContentItemOut.model_validate(item))
    except ValueError as e:
        if str(e) in ("plan_not_found", "tenant_not_found"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e).replace("_", " "),
            ) from e
        if str(e) == "asset_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset not found",
            ) from e
        if str(e) == "day_not_in_plan":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Day not found in plan",
            ) from e
        if str(e) == "day_out_of_range":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="day must be 1..30",
            ) from e
        raise


@router.get("/content/{content_id}", response_model=ContentItemOut)
async def get_content(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ContentItemOut:
    """Get content item by id."""
    item = await get_content_by_id(db, content_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content not found",
        )
    return ContentItemOut.model_validate(item)


@router.get("/content/by_plan/{plan_id}", response_model=List[ContentItemOut])
async def get_content_by_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> List[ContentItemOut]:
    """Get all content items for a plan, ordered by day."""
    items = await get_content_by_plan_id(db, plan_id)
    return [ContentItemOut.model_validate(i) for i in items]
