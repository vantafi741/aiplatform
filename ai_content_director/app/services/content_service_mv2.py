"""
Revenue MVP Module 2: Content Generator.
From generated_plan (plan_json.days) generate content item (title, caption, hashtags, content_type).
HITL by confidence. Log ai_usage_logs. Fallback when no OPENAI_API_KEY.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models import GeneratedPlan, RevenueContentItem, Tenant
from app.services.ai_usage_service import log_usage
from app.services.llm_service import LLMService
from app.services.onboarding_industry_service import get_industry_profile_by_tenant

logger = get_logger(__name__)

# HITL: same as Module 1
HITL_APPROVED_MIN = 0.85
HITL_DRAFT_MIN = 0.70


def approval_status_from_confidence(confidence: float) -> str:
    """Map confidence_score to approval_status (HITL)."""
    if confidence >= HITL_APPROVED_MIN:
        return "APPROVED"
    if confidence >= HITL_DRAFT_MIN:
        return "DRAFT"
    return "ESCALATE"


def _build_brand_context(tenant: Tenant, industry_name: str, industry_desc: Optional[str]) -> Dict[str, Any]:
    """Build context for LLM from tenant + industry_profile."""
    return {
        "industry": tenant.industry,
        "industry_profile_name": industry_name,
        "industry_profile_description": industry_desc or "",
        "main_services": [],
        "brand_tone": "",
        "target_customer": "",
        "cta_style": "",
    }


def _template_content(topic: str, content_angle: str) -> Dict[str, Any]:
    """Fallback template when LLM not configured or fails."""
    return {
        "content_type": "POST",
        "title": f"Bai viet: {topic[:50]}",
        "caption": content_angle or topic,
        "hashtags": ["#content", "#social", "#post", "#brand", "#industry", "#topic"],
        "confidence_score": 0.75,
    }


def _find_day_in_plan_json(plan_json: Dict[str, Any], day: int) -> Optional[Dict[str, Any]]:
    """Get day entry from plan_json.days. Supports 'day' or 'day_number'."""
    days = plan_json.get("days") or []
    for d in days:
        if not isinstance(d, dict):
            continue
        dnum = d.get("day") or d.get("day_number")
        if dnum == day:
            return d
    return None


async def generate_content(
    db: AsyncSession,
    tenant_id: UUID,
    plan_id: UUID,
    day: int,
) -> RevenueContentItem:
    """
    Generate one content item for (tenant, plan, day).
    Uses LLM or fallback. Saves to revenue_content_items. Logs ai_usage_logs.
    """
    if day < 1 or day > 30:
        raise ValueError("day_out_of_range")

    plan_result = await db.execute(select(GeneratedPlan).where(GeneratedPlan.id == plan_id))
    plan = plan_result.scalar_one_or_none()
    if not plan or plan.tenant_id != tenant_id:
        raise ValueError("plan_not_found")

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        raise ValueError("tenant_not_found")

    day_data = _find_day_in_plan_json(plan.plan_json, day)
    if not day_data:
        raise ValueError("day_not_in_plan")

    topic = (day_data.get("topic") or "").strip() or f"Day {day}"
    content_angle = (day_data.get("content_angle") or "").strip() or ""

    profile = await get_industry_profile_by_tenant(db, tenant_id)
    industry_name = profile.name if profile else tenant.industry
    industry_desc = profile.description if profile else None
    brand_context = _build_brand_context(tenant, industry_name, industry_desc)

    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    model_used: Optional[str] = None
    settings = get_settings()
    llm = LLMService(settings)

    try:
        out, usage_info = await llm.generate_single_content(brand_context, topic, content_angle)
        prompt_tokens = usage_info.get("prompt_tokens", 0)
        completion_tokens = usage_info.get("completion_tokens", 0)
        total_tokens = usage_info.get("total_tokens", 0)
        model_used = settings.openai_model
    except (ValueError, Exception) as e:
        logger.warning("content_mv2.llm_fallback", tenant_id=str(tenant_id), plan_id=str(plan_id), day=day, error=str(e))
        out = _template_content(topic, content_angle)
        total_tokens = 0

    hashtags = out.get("hashtags") or []
    if not isinstance(hashtags, list):
        hashtags = [str(hashtags)]
    hashtags = [str(h).strip() for h in hashtags if str(h).strip()][:30]
    if len(hashtags) < 5:
        hashtags = hashtags + ["#tag" + str(i) for i in range(5 - len(hashtags))]

    confidence = float(out.get("confidence_score", 0.75))
    confidence = max(0.0, min(1.0, confidence))
    approval_status = approval_status_from_confidence(confidence)

    item = RevenueContentItem(
        tenant_id=tenant_id,
        plan_id=plan_id,
        day=day,
        topic=topic,
        content_angle=content_angle,
        content_type=(out.get("content_type") or "POST").strip().upper() or "POST",
        title=(out.get("title") or "").strip() or "Untitled",
        caption=(out.get("caption") or "").strip() or "",
        hashtags=hashtags,
        confidence_score=confidence,
        approval_status=approval_status,
    )
    if item.content_type not in ("POST", "REEL", "CAROUSEL"):
        item.content_type = "POST"

    db.add(item)
    await db.flush()
    await db.refresh(item)

    await log_usage(
        db,
        tenant_id=tenant_id,
        feature="content_generator",
        model=model_used or "gpt-4o-mini",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )

    logger.info(
        "content_mv2.generated",
        content_id=str(item.id),
        tenant_id=str(tenant_id),
        plan_id=str(plan_id),
        day=day,
        approval_status=approval_status,
    )
    return item


async def get_content_by_id(
    db: AsyncSession,
    content_id: UUID,
) -> Optional[RevenueContentItem]:
    """Get revenue content item by id."""
    result = await db.execute(select(RevenueContentItem).where(RevenueContentItem.id == content_id))
    return result.scalar_one_or_none()


async def get_content_by_plan_id(
    db: AsyncSession,
    plan_id: UUID,
) -> List[RevenueContentItem]:
    """Get all revenue content items for a plan, ordered by day."""
    result = await db.execute(
        select(RevenueContentItem)
        .where(RevenueContentItem.plan_id == plan_id)
        .order_by(RevenueContentItem.day)
    )
    return list(result.scalars().all())
