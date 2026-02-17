"""Content generation service: sample posts (OpenAI + deterministic fallback)."""
import json
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models import ContentItem, ContentPlan, Tenant, BrandProfile
from app.schemas.content import ContentGenerateSamplesRequest, ContentItemOut
from app.services.ai_usage_service import is_over_budget, log_usage
from app.services.approval_service import log_audit_event, review_state_from_confidence
from app.services.kb_service import query_kb_ilike, build_kb_context_string
from app.services.llm_service import LLMService

logger = get_logger(__name__)

DEFAULT_CONFIDENCE = 0.75


def _make_sample_post(
    day_number: int,
    topic: str,
    industry: str,
    index: int,
) -> Tuple[str, str, str]:
    """Deterministic title, caption, hashtags for one sample post (fallback)."""
    title = f"[{industry}] Ngày {day_number}: {topic}"
    caption = (
        f"Nội dung mẫu cho chủ đề: {topic}. "
        f"Đây là bài viết số {index + 1} trong kế hoạch nội dung. "
        "Chỉnh sửa nội dung trước khi duyệt và đăng."
    )
    hashtags = f"#content #{industry.replace(' ', '')} #day{day_number}"
    return title, caption, hashtags


async def generate_sample_posts(
    db: AsyncSession,
    request: ContentGenerateSamplesRequest,
    force: bool = False,
    use_ai: bool = True,
) -> Tuple[int, List[ContentItemOut], bool, bool, Optional[str]]:
    """
    Create request.count sample content_items (draft) for tenant.
    If use_ai and OpenAI configured and succeeds: use LLM output; else fallback.
    Returns (created_count, items, used_ai, used_fallback, model).
    """
    tenant_id = request.tenant_id
    count = request.count
    settings = get_settings()

    # Cost guard: từ chối count > 20
    if count > 20:
        raise ValueError("count_exceeded")

    q_tenant = select(Tenant).where(Tenant.id == tenant_id)
    r = await db.execute(q_tenant)
    tenant = r.scalar_one_or_none()
    if not tenant:
        raise ValueError("tenant_not_found")
    industry = tenant.industry

    count_q = select(func.count(ContentItem.id)).where(ContentItem.tenant_id == tenant_id)
    r = await db.execute(count_q)
    existing = r.scalar() or 0
    if existing >= count and not force:
        raise ValueError("content_exists")

    q_plans = (
        select(ContentPlan)
        .where(ContentPlan.tenant_id == tenant_id)
        .order_by(ContentPlan.day_number)
    )
    r = await db.execute(q_plans)
    plans = list(r.scalars().all())
    if not plans:
        plan_ids = [None] * count
        topics = [f"Chủ đề mẫu {i + 1}" for i in range(count)]
        day_numbers = list(range(1, count + 1))
    else:
        plan_ids = []
        topics = []
        day_numbers = []
        for i in range(count):
            p = plans[i % len(plans)]
            plan_ids.append(p.id)
            topics.append(p.topic)
            day_numbers.append(p.day_number)

    used_ai = False
    used_fallback = False
    model_used: Optional[str] = None
    posts_data: List[Tuple[Optional[UUID], int, str, str, str, float]] = []

    if use_ai and settings.openai_api_key:
        try:
            if await is_over_budget(db, tenant_id):
                raise ValueError("budget_exceeded")
            llm = LLMService(settings)
            q_profile = select(BrandProfile).where(BrandProfile.tenant_id == tenant_id)
            rp = await db.execute(q_profile)
            profile = rp.scalar_one_or_none()
            brand_context = {
                "industry": industry,
                "brand_tone": (profile.brand_tone or "") if profile else "",
                "cta_style": (profile.cta_style or "") if profile else "",
            }
            plan_items = [
                {"day_number": p.day_number, "topic": p.topic, "content_angle": p.content_angle or ""}
                for p in plans[:count]
            ]
            if len(plan_items) < count and plans:
                while len(plan_items) < count:
                    p = plans[len(plan_items) % len(plans)]
                    plan_items.append({"day_number": p.day_number, "topic": p.topic, "content_angle": p.content_angle or ""})

            # Query KB theo chủ đề / industry để inject vào prompt
            kb_context_str = ""
            kb_hit_count = 0
            kb_chars_used = 0
            search_parts = list(set(topics)) + [industry]
            if profile and getattr(profile, "main_services", None):
                try:
                    ms = profile.main_services
                    if isinstance(ms, str):
                        arr = json.loads(ms) if ms.strip().startswith("[") else []
                    else:
                        arr = ms if isinstance(ms, list) else []
                    search_parts.extend(arr)
                except Exception:
                    pass
            query_str = " ".join(str(x) for x in search_parts if x)[:300]
            if query_str:
                kb_items = await query_kb_ilike(db, tenant_id=tenant_id, query=query_str, top_k=10)
                kb_context_str, kb_hit_count, kb_chars_used = build_kb_context_string(kb_items)
                logger.info(
                    "content.kb_context",
                    kb_hit_count=kb_hit_count,
                    kb_chars_used=kb_chars_used,
                    tenant_id=str(tenant_id),
                )
            raw, usage_info = await llm.generate_sample_posts(
                brand_context, plan_items[:count], count, kb_context=kb_context_str or None
            )
            if len(raw) != count:
                raise ValueError("invalid_samples_output")
            await log_usage(
                db,
                tenant_id=tenant_id,
                feature="content_samples",
                model=settings.openai_model,
                prompt_tokens=usage_info.get("prompt_tokens", 0),
                completion_tokens=usage_info.get("completion_tokens", 0),
                total_tokens=usage_info.get("total_tokens", 0),
            )
            for i, row in enumerate(raw):
                conf = row.get("confidence_score", 0.75)
                if not (0 <= conf <= 1):
                    conf = max(0.0, min(1.0, float(conf)))
                plan_id = plan_ids[i] if i < len(plan_ids) else None
                day_num = day_numbers[i] if i < len(day_numbers) else i + 1
                posts_data.append((
                    plan_id,
                    day_num,
                    row.get("title") or "Untitled",
                    row.get("caption") or "",
                    row.get("hashtags") or "",
                    conf,
                ))
            used_ai = True
            model_used = settings.openai_model
        except ValueError as e:
            if str(e) == "budget_exceeded":
                logger.info("content.budget_exceeded", tenant_id=str(tenant_id))
                used_fallback = True
                for i in range(count):
                    plan_id = plan_ids[i]
                    day_number = day_numbers[i]
                    topic = topics[i]
                    title, caption, hashtags = _make_sample_post(day_number, topic, industry, i)
                    posts_data.append((plan_id, day_number, title, caption, hashtags, DEFAULT_CONFIDENCE))
            else:
                raise
        except Exception as e:
            logger.info("content.llm_fallback", reason=str(e))
            used_fallback = True
            for i in range(count):
                plan_id = plan_ids[i]
                day_number = day_numbers[i]
                topic = topics[i]
                title, caption, hashtags = _make_sample_post(day_number, topic, industry, i)
                posts_data.append((plan_id, day_number, title, caption, hashtags, DEFAULT_CONFIDENCE))
    elif use_ai and not settings.openai_api_key:
        used_fallback = True
        for i in range(count):
            plan_id = plan_ids[i]
            day_number = day_numbers[i]
            topic = topics[i]
            title, caption, hashtags = _make_sample_post(day_number, topic, industry, i)
            posts_data.append((plan_id, day_number, title, caption, hashtags, DEFAULT_CONFIDENCE))
    else:
        for i in range(count):
            plan_id = plan_ids[i]
            day_number = day_numbers[i]
            topic = topics[i]
            title, caption, hashtags = _make_sample_post(day_number, topic, industry, i)
            posts_data.append((plan_id, day_number, title, caption, hashtags, DEFAULT_CONFIDENCE))

    created_items: List[ContentItemOut] = []
    now_utc = datetime.now(timezone.utc)
    for plan_id, _day_num, title, caption, hashtags, confidence in posts_data:
        item = ContentItem(
            tenant_id=tenant_id,
            plan_id=plan_id,
            title=title,
            caption=caption,
            hashtags=hashtags,
            status="draft",
            confidence_score=confidence,
        )
        db.add(item)
        await db.flush()

        # HITL: review_state theo confidence; auto_approved -> status=approved
        review_state = review_state_from_confidence(confidence)
        item.review_state = review_state
        if review_state == "auto_approved":
            item.status = "approved"
            item.approved_at = now_utc
            await log_audit_event(
                db,
                tenant_id=tenant_id,
                content_id=item.id,
                event_type="AUTO_APPROVED",
                actor="SYSTEM",
                metadata_={"confidence_score": confidence},
            )
        elif review_state == "needs_review":
            await log_audit_event(
                db,
                tenant_id=tenant_id,
                content_id=item.id,
                event_type="NEEDS_REVIEW",
                actor="SYSTEM",
                metadata_={"confidence_score": confidence},
            )
        else:
            await log_audit_event(
                db,
                tenant_id=tenant_id,
                content_id=item.id,
                event_type="ESCALATED",
                actor="SYSTEM",
                metadata_={"confidence_score": confidence},
            )
        await db.flush()

        created_items.append(
            ContentItemOut(
                id=item.id,
                title=item.title,
                caption=item.caption,
                hashtags=item.hashtags,
                status=item.status,
                confidence_score=item.confidence_score,
                review_state=item.review_state,
                approved_at=item.approved_at,
                rejected_at=item.rejected_at,
                scheduled_at=item.scheduled_at,
                schedule_status=item.schedule_status,
                publish_attempts=item.publish_attempts,
                last_publish_error=item.last_publish_error,
                last_publish_at=item.last_publish_at,
            )
        )

    # Audit: một event GENERATE_CONTENT cho cả batch
    await log_audit_event(
        db,
        tenant_id=tenant_id,
        event_type="GENERATE_CONTENT",
        actor="SYSTEM",
        content_id=None,
        metadata_={"count": len(created_items), "model": model_used, "used_fallback": used_fallback},
    )

    logger.info(
        "content.samples_generated",
        tenant_id=str(tenant_id),
        created=len(created_items),
        used_ai=used_ai,
        used_fallback=used_fallback,
    )
    return len(created_items), created_items, used_ai, used_fallback, model_used


async def list_content(
    db: AsyncSession,
    tenant_id: UUID,
    status: Optional[str] = None,
) -> List[ContentItemOut]:
    """
    Liệt kê content items của tenant, có thể lọc theo status (draft | approved | published).
    """
    q = select(ContentItem).where(ContentItem.tenant_id == tenant_id).order_by(ContentItem.created_at.desc())
    if status:
        q = q.where(ContentItem.status == status)
    r = await db.execute(q)
    items = list(r.scalars().all())
    return [
        ContentItemOut(
            id=it.id,
            title=it.title,
            caption=it.caption,
            hashtags=it.hashtags,
            status=it.status,
            confidence_score=it.confidence_score,
            review_state=it.review_state,
            approved_at=it.approved_at,
            rejected_at=it.rejected_at,
            scheduled_at=it.scheduled_at,
            schedule_status=it.schedule_status,
            publish_attempts=it.publish_attempts,
            last_publish_error=it.last_publish_error,
            last_publish_at=it.last_publish_at,
        )
        for it in items
    ]


async def schedule_content(
    db: AsyncSession,
    tenant_id: UUID,
    content_id: UUID,
    scheduled_at: datetime,
    actor: str = "HUMAN",
) -> ContentItem:
    """
    Đặt lịch đăng: chỉ với content đã approved.
    Set scheduled_at, schedule_status='scheduled'. Ghi audit SCHEDULE_SET.
    """
    r = await db.execute(
        select(ContentItem).where(
            ContentItem.id == content_id,
            ContentItem.tenant_id == tenant_id,
        )
    )
    item = r.scalar_one_or_none()
    if not item:
        raise ValueError("content_not_found")
    if item.status != "approved":
        raise ValueError("content_not_approved")
    item.scheduled_at = scheduled_at
    item.schedule_status = "scheduled"
    await db.flush()
    await log_audit_event(
        db,
        tenant_id=tenant_id,
        content_id=content_id,
        event_type="SCHEDULE_SET",
        actor=actor,
        metadata_={"scheduled_at": scheduled_at.isoformat()},
    )
    logger.info("content.scheduled", content_id=str(content_id), scheduled_at=scheduled_at.isoformat())
    return item


async def unschedule_content(
    db: AsyncSession,
    tenant_id: UUID,
    content_id: UUID,
    actor: str = "HUMAN",
) -> ContentItem:
    """Xóa lịch: set scheduled_at=None, schedule_status='none'. Ghi audit SCHEDULE_CLEARED."""
    r = await db.execute(
        select(ContentItem).where(
            ContentItem.id == content_id,
            ContentItem.tenant_id == tenant_id,
        )
    )
    item = r.scalar_one_or_none()
    if not item:
        raise ValueError("content_not_found")
    item.scheduled_at = None
    item.schedule_status = "none"
    await db.flush()
    await log_audit_event(
        db,
        tenant_id=tenant_id,
        content_id=content_id,
        event_type="SCHEDULE_CLEARED",
        actor=actor,
        metadata_={},
    )
    logger.info("content.unscheduled", content_id=str(content_id))
    return item
