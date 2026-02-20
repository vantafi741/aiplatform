"""30-day content planner service (OpenAI + deterministic fallback)."""
import json
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models import ContentPlan, Tenant, BrandProfile
from app.schemas.planner import PlanItemOut, PlannerGenerateRequest
from app.services.ai_usage_service import is_over_budget, log_usage
from app.services.approval_service import log_audit_event
from app.services.llm_service import LLMService

logger = get_logger(__name__)


def _build_plan_topics(
    industry: str,
    main_services_list: List[str],
    brand_tone: str,
    days: int,
) -> List[Tuple[int, str, str]]:
    """
    Build deterministic (day_number, topic, content_angle) for 1..days.
    Fallback when LLM is not used or fails.
    """
    result = []
    templates = [
        (1, f"Giới thiệu {industry}", f"Giới thiệu ngắn gọn về lĩnh vực {industry} và giá trị bạn mang lại."),
        (2, "Giới thiệu dịch vụ chính", "Điểm nổi bật của dịch vụ hàng đầu."),
        (3, "Khách hàng mục tiêu", "Ai là khách hàng lý tưởng và vì sao họ cần bạn."),
        (4, "Case study / Thành tựu", "Một dự án hoặc thành tựu điển hình."),
        (5, "Quy trình làm việc", "Các bước từ tiếp nhận đến hoàn thành."),
        (6, "Chất lượng & Cam kết", "Cam kết chất lượng và tiêu chuẩn."),
        (7, "Tips & Kiến thức", "Mẹo hay hoặc kiến thức hữu ích trong ngành."),
        (8, "FAQ", "Câu hỏi thường gặp và trả lời ngắn."),
        (9, "Ưu đãi / CTA", "Kêu gọi hành động hoặc ưu đãi hiện có."),
        (10, "Tổng kết tuần", "Tóm tắt nội dung đã chia sẻ và nhắc CTA."),
    ]
    for d in range(1, days + 1):
        idx = (d - 1) % len(templates)
        day_num, topic_tpl, angle_tpl = templates[idx]
        topic = topic_tpl if d <= 10 else f"{industry} - Chủ đề ngày {d}"
        angle = angle_tpl if d <= 10 else f"Nội dung hữu ích về {industry} cho ngày {d}."
        result.append((d, topic, angle))
    return result


def _brand_context(tenant: Tenant, profile: Optional[BrandProfile]) -> dict:
    """Build brand_context dict for LLM from tenant + profile."""
    main_services_list = []
    if profile and profile.main_services:
        try:
            main_services_list = json.loads(profile.main_services)
        except Exception:
            main_services_list = []
    return {
        "industry": tenant.industry or "",
        "main_services": main_services_list,
        "brand_tone": (profile.brand_tone or "") if profile else "",
        "target_customer": (profile.target_customer or "") if profile else "",
        "cta_style": (profile.cta_style or "") if profile else "",
    }


async def get_tenant_with_profile(
    db: AsyncSession,
    tenant_id: UUID,
) -> Optional[Tuple[Tenant, Optional[BrandProfile]]]:
    """Load tenant and optional brand profile by tenant_id."""
    q_tenant = select(Tenant).where(Tenant.id == tenant_id)
    r = await db.execute(q_tenant)
    tenant = r.scalar_one_or_none()
    if not tenant:
        return None
    q_profile = select(BrandProfile).where(BrandProfile.tenant_id == tenant_id)
    rp = await db.execute(q_profile)
    profile = rp.scalar_one_or_none()
    return (tenant, profile)


async def generate_30_day_plan(
    db: AsyncSession,
    request: PlannerGenerateRequest,
    force: bool = False,
    use_ai: bool = True,
) -> Tuple[int, List[PlanItemOut], bool, bool, Optional[str]]:
    """
    Create request.days content_plans for tenant.
    If use_ai and OpenAI configured and succeeds: use LLM output; else fallback to deterministic template.
    Returns (created_count, items, used_ai, used_fallback, model).
    Raises ValueError("tenant_not_found") or ValueError("plan_exists") as before.
    """
    tenant_id = request.tenant_id
    days = request.days
    settings = get_settings()

    # Cost guard: từ chối days > 30
    if days > 30:
        raise ValueError("days_exceeded")

    pair = await get_tenant_with_profile(db, tenant_id)
    if not pair:
        raise ValueError("tenant_not_found")
    tenant, profile = pair
    industry = tenant.industry
    main_services_list = []
    if profile and profile.main_services:
        try:
            main_services_list = json.loads(profile.main_services)
        except Exception:
            main_services_list = []
    brand_tone = (profile.brand_tone or "") if profile else ""

    count_q = select(func.count(ContentPlan.id)).where(ContentPlan.tenant_id == tenant_id)
    r = await db.execute(count_q)
    existing = r.scalar() or 0
    if existing >= days and not force:
        raise ValueError("plan_exists")

    if force and existing >= days:
        await db.execute(delete(ContentPlan).where(ContentPlan.tenant_id == tenant_id))
        await db.flush()

    used_ai = False
    used_fallback = False
    model_used: Optional[str] = None
    topics: List[Tuple[int, str, str]] = []

    if use_ai is True and settings.openai_api_key:
        try:
            if await is_over_budget(db, tenant_id):
                raise ValueError("budget_exceeded")
            llm = LLMService(settings)
            brand_context = _brand_context(tenant, profile)
            raw, usage_info = await llm.generate_planner(brand_context, days)
            if len(raw) == days and len(set(r["day_number"] for r in raw)) == days:
                await log_usage(
                    db,
                    tenant_id=tenant_id,
                    feature="planner",
                    model=settings.openai_model,
                    prompt_tokens=usage_info.get("prompt_tokens", 0),
                    completion_tokens=usage_info.get("completion_tokens", 0),
                    total_tokens=usage_info.get("total_tokens", 0),
                )
                raw_sorted = sorted(raw, key=lambda x: x["day_number"])
                topics = [(r["day_number"], r["topic"], r.get("content_angle") or "") for r in raw_sorted]
                used_ai = True
                model_used = settings.openai_model
            else:
                raise ValueError("invalid_planner_output")
        except ValueError as e:
            if str(e) == "budget_exceeded":
                logger.info("planner.budget_exceeded", tenant_id=str(tenant_id))
                used_fallback = True
                topics = _build_plan_topics(industry, main_services_list, brand_tone, days)
            else:
                raise
        except Exception as e:
            logger.info("planner.llm_fallback", reason=str(e))
            used_fallback = True
            topics = _build_plan_topics(industry, main_services_list, brand_tone, days)
    elif use_ai is True and not settings.openai_api_key:
        used_fallback = True
        topics = _build_plan_topics(industry, main_services_list, brand_tone, days)
    else:
        topics = _build_plan_topics(industry, main_services_list, brand_tone, days)

    created_items: List[PlanItemOut] = []
    for day_number, topic, content_angle in topics:
        plan = ContentPlan(
            tenant_id=tenant_id,
            day_number=day_number,
            topic=topic,
            content_angle=content_angle,
            status="planned",
        )
        db.add(plan)
        await db.flush()
        created_items.append(
            PlanItemOut(
                day_number=day_number,
                topic=topic,
                content_angle=content_angle,
                status="planned",
            )
        )
    # Audit: ghi event GENERATE_PLAN
    await log_audit_event(
        db,
        tenant_id=tenant_id,
        event_type="GENERATE_PLAN",
        actor="SYSTEM",
        content_id=None,
        metadata_={"days": days, "model": model_used, "used_fallback": used_fallback},
    )

    logger.info(
        "planner.generated",
        tenant_id=str(tenant_id),
        created=len(created_items),
        used_ai=used_ai,
        used_fallback=used_fallback,
    )
    return len(created_items), created_items, used_ai, used_fallback, model_used
