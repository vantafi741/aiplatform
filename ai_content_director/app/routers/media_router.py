"""Media analyze API router (content_assets -> asset_summaries)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.asset_summary import MediaAnalyzeRequest, MediaAnalyzeResponse
from app.services.asset_summary_service import get_or_create_asset_summary

router = APIRouter(prefix="/api", tags=["media"])


@router.post("/media/analyze", response_model=MediaAnalyzeResponse)
async def post_media_analyze(
    payload: MediaAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
) -> MediaAnalyzeResponse:
    """
    Analyze media từ content_assets và cache vào asset_summaries.
    Nếu đã có cache (tenant_id, asset_id) thì trả lại ngay.
    """
    try:
        summary, cached = await get_or_create_asset_summary(
            db=db,
            tenant_id=payload.tenant_id,
            asset_id=payload.asset_id,
        )
    except ValueError as err:
        message = str(err)
        if message == "asset_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset not found",
            ) from err
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message) from err
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"media_analyze_failed: {err}",
        ) from err

    return MediaAnalyzeResponse(
        summary_id=summary.id,
        asset_id=summary.asset_id,
        tenant_id=summary.tenant_id,
        summary=summary.summary,
        insights_json=summary.insights_json or {},
        suggested_angle=summary.suggested_angle or "",
        suggested_tone=summary.suggested_tone or "",
        confidence_score=float(summary.confidence_score or 0.0),
        cached=cached,
        created_at=summary.created_at,
    )
