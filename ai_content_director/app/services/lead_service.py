"""
AI Lead System: xử lý webhook Facebook -> lead_signals, classify, audit, n8n follow-up.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models import LeadSignal, Tenant
from app.schemas.leads import LeadSignalOut, LeadListResponse
from app.services.approval_service import log_audit_event
from app.services.lead_classify_service import classify_intent
from app.services.n8n_webhook_service import notify_n8n_lead_follow_up

logger = get_logger(__name__)


def _status_from_confidence(confidence_score: Optional[float]) -> str:
    """
    HITL: >=0.85 auto; 0.70-0.85 draft; <0.70 escalate.
    Map sang status lead: new_auto | new_draft | new_escalate.
    """
    if confidence_score is None:
        return "new_escalate"
    if confidence_score >= 0.85:
        return "new_auto"
    if confidence_score >= 0.70:
        return "new_draft"
    return "new_escalate"


def _extract_messages_from_facebook_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Từ payload Facebook webhook (object=page, entry[]) trích danh sách message/comment.
    Hỗ trợ: (1) Real messaging: entry[].messaging[] (inbox). (2) Real comment: entry[].changes[].value.
    (3) Mock: entry[] có message/comment_id/sender_name ở top level.
    Mỗi phần tử: source_type, source_subtype, text, author_name, author_id, external_*_id, meta.
    """
    messages: List[Dict[str, Any]] = []
    entries = payload.get("entry") or []

    for entry in entries:
        # 1) Real: entry.changes[] (Facebook Page subscription comment)
        changes = entry.get("changes") or []
        for change in changes:
            val = change.get("value") or {}
            comment_id = val.get("comment_id")
            if not comment_id:
                continue
            message_text = val.get("message") or ""
            sender_name = val.get("sender_name")
            sender_id = val.get("sender_id")
            post_id = val.get("post_id") or val.get("parent_id")
            created_time = val.get("created_time")
            messages.append({
                "source_type": "comment",
                "source_subtype": "post_comment",
                "text": message_text,
                "author_id": str(sender_id) if sender_id else None,
                "author_name": sender_name,
                "external_post_id": str(post_id) if post_id else None,
                "external_message_id": str(comment_id),
                "external_thread_id": str(post_id) if post_id else None,
                "meta": {"created_time": created_time, "raw": change},
            })

        # 2) Real: entry.messaging[] (inbox)
        messaging = entry.get("messaging") or []
        for msg in messaging:
            text = (msg.get("message") or {}).get("text") or ""
            sender = msg.get("sender") or {}
            sid = sender.get("id")
            mid = (msg.get("message") or {}).get("mid")
            messages.append({
                "source_type": "message",
                "source_subtype": "inbox",
                "text": text,
                "author_id": str(sid) if sid else None,
                "author_name": None,
                "external_post_id": None,
                "external_message_id": str(mid) if mid else None,
                "external_thread_id": str(sid) if sid else None,
                "meta": {"raw": msg},
            })

        # 3) Mock hoặc entry có message/comment_id ở top level (không có changes/messaging)
        if not changes and not messaging:
            comment_id = entry.get("comment_id")
            message_text = entry.get("message") or ""
            sender_name = entry.get("sender_name")
            sender_id = entry.get("sender_id")
            post_id = entry.get("post_id")
            # Mock: có message hoặc comment_id
            if message_text or comment_id:
                messages.append({
                    "source_type": entry.get("source_type", "comment"),
                    "source_subtype": entry.get("source_subtype", "post_comment"),
                    "text": message_text,
                    "author_id": str(sender_id) if sender_id else None,
                    "author_name": sender_name,
                    "external_post_id": str(post_id) if post_id else None,
                    "external_message_id": str(comment_id) if comment_id else None,
                    "external_thread_id": str(post_id) if post_id else None,
                    "meta": {"raw": entry},
                })
    return messages


async def process_facebook_webhook(
    db: AsyncSession,
    tenant_id: UUID,
    payload: Dict[str, Any],
) -> List[UUID]:
    """
    Xử lý payload POST /webhooks/facebook: trích messages, classify, ghi lead_signals,
    audit LEAD_SIGNAL_CREATED, gọi n8n khi priority=high.
    Trả về danh sách lead_signal id đã tạo (bỏ qua trùng external_message_id).
    """
    # Kiểm tra tenant tồn tại
    r = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    if r.scalar_one_or_none() is None:
        logger.warning("lead_service.tenant_not_found", tenant_id=str(tenant_id))
        return []

    messages = _extract_messages_from_facebook_payload(payload)
    if not messages:
        logger.info("lead_service.webhook_no_messages", tenant_id=str(tenant_id))
        return []

    created_ids: List[UUID] = []
    for m in messages:
        text = (m.get("text") or "").strip()
        external_message_id = m.get("external_message_id")
        if isinstance(external_message_id, dict):
            external_message_id = None
        if external_message_id and not isinstance(external_message_id, str):
            external_message_id = str(external_message_id)

        # Trùng message (unique constraint): bỏ qua
        if external_message_id:
            r = await db.execute(
                select(LeadSignal.id).where(
                    LeadSignal.tenant_id == tenant_id,
                    LeadSignal.platform == "facebook",
                    LeadSignal.external_message_id == external_message_id,
                )
            )
            if r.scalar_one_or_none() is not None:
                logger.debug("lead_service.duplicate_skipped", external_message_id=external_message_id)
                continue

        # Classify intent (rule-first; LLM optional)
        classify_result = await classify_intent(text or None)
        status = _status_from_confidence(classify_result.confidence_score)

        lead = LeadSignal(
            tenant_id=tenant_id,
            platform="facebook",
            source_type=m.get("source_type") or "comment",
            source_subtype=m.get("source_subtype"),
            content_id=None,
            publish_log_id=None,
            external_post_id=m.get("external_post_id"),
            external_thread_id=m.get("external_thread_id"),
            external_message_id=external_message_id,
            author_name=m.get("author_name"),
            author_id=m.get("author_id"),
            content_text=text or None,
            intent_label=classify_result.intent_label,
            priority=classify_result.priority,
            confidence_score=classify_result.confidence_score,
            status=status,
            assignee=None,
            follow_up_at=None,
            last_contact_at=None,
            meta=m.get("meta") or {},
        )
        db.add(lead)
        await db.flush()

        logger.info(
            "lead_signal.created",
            lead_id=str(lead.id),
            tenant_id=str(tenant_id),
            intent=classify_result.intent_label,
            priority=classify_result.priority,
            confidence=classify_result.confidence_score,
            status=status,
        )

        await log_audit_event(
            db,
            tenant_id=tenant_id,
            event_type="LEAD_SIGNAL_CREATED",
            actor="SYSTEM",
            content_id=None,
            metadata_={"lead_signal_id": str(lead.id), "intent": classify_result.intent_label, "priority": classify_result.priority},
        )

        if classify_result.priority == "high":
            await notify_n8n_lead_follow_up(
                lead.id,
                tenant_id,
                {
                    "author_name": lead.author_name,
                    "author_id": lead.author_id,
                    "content_text": lead.content_text,
                    "intent_label": lead.intent_label,
                    "priority": lead.priority,
                },
            )

        created_ids.append(lead.id)

    return created_ids


def _lead_to_out(lead: LeadSignal) -> LeadSignalOut:
    """Map ORM LeadSignal -> LeadSignalOut."""
    return LeadSignalOut(
        id=lead.id,
        tenant_id=lead.tenant_id,
        platform=lead.platform,
        source_type=lead.source_type,
        source_subtype=lead.source_subtype,
        content_id=lead.content_id,
        publish_log_id=lead.publish_log_id,
        external_post_id=lead.external_post_id,
        external_thread_id=lead.external_thread_id,
        external_message_id=lead.external_message_id,
        author_name=lead.author_name,
        author_id=lead.author_id,
        content_text=lead.content_text,
        intent_label=lead.intent_label,
        priority=lead.priority,
        confidence_score=lead.confidence_score,
        status=lead.status,
        assignee=lead.assignee,
        follow_up_at=lead.follow_up_at,
        last_contact_at=lead.last_contact_at,
        meta=lead.meta or {},
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


async def list_leads(
    db: AsyncSession,
    tenant_id: UUID,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> LeadListResponse:
    """Lấy danh sách lead signals của tenant (GET /api/leads)."""
    q = select(LeadSignal).where(LeadSignal.tenant_id == tenant_id)
    if status:
        q = q.where(LeadSignal.status == status)
    q = q.order_by(LeadSignal.created_at.desc())

    # Count total
    from sqlalchemy import func
    count_q = select(func.count(LeadSignal.id)).where(LeadSignal.tenant_id == tenant_id)
    if status:
        count_q = count_q.where(LeadSignal.status == status)
    r_count = await db.execute(count_q)
    total = r_count.scalar_one_or_none() or 0

    r = await db.execute(q.offset(offset).limit(limit))
    leads = list(r.scalars().all())
    return LeadListResponse(
        tenant_id=tenant_id,
        leads=[_lead_to_out(lead) for lead in leads],
        total=total,
    )
