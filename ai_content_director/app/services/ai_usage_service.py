"""AI usage logging + daily budget check (cost guard)."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    get_settings,
    DEFAULT_OPENAI_INPUT_PRICE_PER_1M,
    DEFAULT_OPENAI_OUTPUT_PRICE_PER_1M,
)
from app.logging_config import get_logger
from app.models import AiUsageLog

logger = get_logger(__name__)


def compute_cost_usd(
    prompt_tokens: int,
    completion_tokens: int,
    model: Optional[str] = None,
) -> Decimal:
    """
    Tính cost USD từ token counts (bảng giá static từ config).
    model không dùng để chọn bảng giá trong phiên bản tối giản; dùng chung giá gpt-4o-mini.
    """
    settings = get_settings()
    in_p = (settings.openai_input_price_per_1m or DEFAULT_OPENAI_INPUT_PRICE_PER_1M) / 1_000_000
    out_p = (settings.openai_output_price_per_1m or DEFAULT_OPENAI_OUTPUT_PRICE_PER_1M) / 1_000_000
    return Decimal(str(prompt_tokens * in_p + completion_tokens * out_p)).quantize(Decimal("0.000001"))


async def log_usage(
    db: AsyncSession,
    tenant_id: UUID,
    feature: str,
    model: Optional[str],
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> AiUsageLog:
    """
    Ghi một dòng ai_usage_logs và trả về record.
    cost_usd tính từ compute_cost_usd. Caller đảm bảo commit.
    """
    cost = compute_cost_usd(prompt_tokens, completion_tokens, model)
    log = AiUsageLog(
        tenant_id=tenant_id,
        feature=feature,
        model=model or "",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost,
    )
    db.add(log)
    await db.flush()
    logger.info(
        "ai_usage.logged",
        tenant_id=str(tenant_id),
        feature=feature,
        model=model,
        total_tokens=total_tokens,
        cost_usd=str(cost),
    )
    return log


async def get_daily_total_usd(db: AsyncSession, tenant_id: UUID) -> Decimal:
    """Tổng cost_usd trong ngày (UTC) cho tenant."""
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    q = (
        select(func.coalesce(func.sum(AiUsageLog.cost_usd), 0))
        .where(AiUsageLog.tenant_id == tenant_id)
        .where(AiUsageLog.created_at >= start_of_day)
    )
    r = await db.execute(q)
    val = r.scalar()
    return val if isinstance(val, Decimal) else Decimal("0")


async def is_over_budget(db: AsyncSession, tenant_id: UUID) -> bool:
    """
    True nếu tenant đã vượt DAILY_BUDGET_USD trong ngày.
    Khi True, caller nên fallback template (không gọi OpenAI).
    """
    settings = get_settings()
    total = await get_daily_total_usd(db, tenant_id)
    return total >= Decimal(str(settings.daily_budget_usd))
