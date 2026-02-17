"""KPI summary API (post metrics) + fetch-now thủ công."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.db import get_db
from app.schemas.kpi import (
    KpiFetchNowRequest,
    KpiFetchNowResponse,
    KpiPostSummary,
    KpiSummaryResponse,
    KpiTotals,
)
from app.services.facebook_metrics_service import fetch_now_metrics, get_kpi_summary
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/kpi", tags=["kpi"])


@router.get("/summary", response_model=KpiSummaryResponse)
async def get_kpi_summary_endpoint(
    tenant_id: UUID = Query(..., description="Tenant UUID"),
    days: int = Query(7, ge=1, le=90, description="Số ngày gần đây"),
    db: AsyncSession = Depends(get_db),
) -> KpiSummaryResponse:
    """Tổng hợp KPI từ post_metrics (reach, impressions, reactions, comments, shares) trong `days` ngày."""
    totals, posts = await get_kpi_summary(db, tenant_id=tenant_id, days=days)
    return KpiSummaryResponse(
        tenant_id=tenant_id,
        range_days=days,
        totals=KpiTotals(**totals),
        posts=[KpiPostSummary(**p) for p in posts],
    )


@router.post("/fetch-now", response_model=KpiFetchNowResponse)
async def post_kpi_fetch_now(
    payload: KpiFetchNowRequest,
    db: AsyncSession = Depends(get_db),
) -> KpiFetchNowResponse:
    """
    Thu thập metrics Facebook ngay (không đợi vòng 6h). Cho demo và vận hành.
    Chỉ lấy bài đăng thành công trong `days` ngày, tối đa `limit` bài (days ≤ 30, limit ≤ 50).
    """
    fetched, success, fail = await fetch_now_metrics(
        db,
        tenant_id=payload.tenant_id,
        days=payload.days,
        limit=payload.limit,
    )
    return KpiFetchNowResponse(
        tenant_id=payload.tenant_id,
        fetched=fetched,
        success=success,
        fail=fail,
    )
