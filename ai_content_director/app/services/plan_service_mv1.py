"""
Revenue MVP Module 1: Generate 30-day plan, strict JSON schema, HITL, ai_usage_logs.
"""
from datetime import date, timedelta
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models import GeneratedPlan, Tenant
from app.schemas.revenue_mv1 import PlanJsonSchema, PlanDayItem

from app.services.ai_usage_service import log_usage
from app.services.llm_service import LLMService
from app.services.onboarding_industry_service import get_industry_profile_by_tenant

logger = get_logger(__name__)

# HITL: confidence >= 0.85 => APPROVED, 0.70-0.85 => DRAFT, <0.70 => ESCALATE
HITL_APPROVED_MIN = 0.85
HITL_DRAFT_MIN = 0.70


def approval_status_from_confidence(confidence: float) -> str:
    """Map confidence_score to approval_status (HITL)."""
    if confidence >= HITL_APPROVED_MIN:
        return "APPROVED"
    if confidence >= HITL_DRAFT_MIN:
        return "DRAFT"
    return "ESCALATE"


def _build_brand_context(
    tenant: Tenant, industry_name: str, industry_description: Any
) -> Dict[str, Any]:
    """Build context dict for LLM from tenant + industry_profile."""
    return {
        "industry": tenant.industry,
        "industry_profile_name": industry_name,
        "industry_profile_description": industry_description or "",
        "main_services": [],
        "brand_tone": "",
        "target_customer": "",
        "cta_style": "",
    }


def _template_plan_30_days() -> List[Dict[str, Any]]:
    """Fallback: 30-day template when LLM not configured or fails."""
    out = []
    for d in range(1, 31):
        out.append({
            "day": d,
            "topic": f"Chu de ngay {d}",
            "content_angle": f"Goc noi dung ngay {d}.",
        })
    return out


async def generate_plan(
    db: AsyncSession,
    tenant_id: UUID,
    start_date: date | None = None,
) -> GeneratedPlan:
    """
    Generate 30-day plan for tenant. Strict JSON schema. Log usage. HITL sets approval_status.
    """
    if start_date is None:
        start_date = date.today()
    end_date = start_date + timedelta(days=29)

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise ValueError("tenant_not_found")

    profile = await get_industry_profile_by_tenant(db, tenant_id)
    industry_name = profile.name if profile else tenant.industry
    industry_description = profile.description if profile else None
    brand_context = _build_brand_context(tenant, industry_name, industry_description or "")

    plan_json_dict: Dict[str, Any]
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    model_used: str | None = None
    confidence = 0.80  # default placeholder

    settings = get_settings()
    llm = LLMService(settings)

    try:
        days_list, usage_info = await llm.generate_planner(brand_context, 30)
        prompt_tokens = usage_info.get("prompt_tokens", 0)
        completion_tokens = usage_info.get("completion_tokens", 0)
        total_tokens = usage_info.get("total_tokens", 0)
        model_used = settings.openai_model
        # Convert day_number -> day for our schema
        days_for_schema = [
            {"day": d["day_number"], "topic": d["topic"], "content_angle": d.get("content_angle")}
            for d in days_list
        ]
        validated = PlanJsonSchema(days=[PlanDayItem(**x) for x in days_for_schema])
        plan_json_dict = validated.model_dump()
        confidence = 0.85  # LLM success -> high confidence placeholder
    except (ValueError, Exception) as e:
        logger.warning("plan_mv1.llm_fallback", tenant_id=str(tenant_id), error=str(e))
        days_raw = _template_plan_30_days()
        validated = PlanJsonSchema(days=[PlanDayItem(**x) for x in days_raw])
        plan_json_dict = validated.model_dump()
        confidence = 0.75  # template -> DRAFT
        total_tokens = 0

    approval_status = approval_status_from_confidence(confidence)

    plan = GeneratedPlan(
        tenant_id=tenant_id,
        start_date=start_date,
        end_date=end_date,
        plan_json=plan_json_dict,
        confidence_score=confidence,
        approval_status=approval_status,
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)

    await log_usage(
        db,
        tenant_id=tenant_id,
        feature="planner_30d",
        model=model_used,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )

    logger.info(
        "plan_mv1.generated",
        plan_id=str(plan.id),
        tenant_id=str(tenant_id),
        approval_status=approval_status,
        confidence=confidence,
    )
    return plan


async def get_plan_by_id(db: AsyncSession, plan_id: UUID) -> GeneratedPlan | None:
    """Get generated plan by id."""
    result = await db.execute(select(GeneratedPlan).where(GeneratedPlan.id == plan_id))
    return result.scalar_one_or_none()
