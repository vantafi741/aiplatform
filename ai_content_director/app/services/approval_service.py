"""
HITL Approval workflow + audit log.
- Ghi audit event (GENERATE_PLAN, GENERATE_CONTENT, AUTO_APPROVED, NEEDS_REVIEW, ESCALATED, APPROVED, REJECTED).
- approve_content / reject_content cho duyệt thủ công.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models import ApprovalEvent, ContentItem

logger = get_logger(__name__)

# Ngưỡng confidence -> review_state
AUTO_APPROVE_THRESHOLD = 0.85
NEEDS_REVIEW_THRESHOLD = 0.70


def review_state_from_confidence(confidence_score: Optional[float]) -> str:
    """
    Xác định review_state từ confidence_score.
    >= 0.85: auto_approved
    0.70 - 0.85: needs_review
    < 0.70: escalate_required
    """
    if confidence_score is None:
        return "needs_review"
    if confidence_score >= AUTO_APPROVE_THRESHOLD:
        return "auto_approved"
    if confidence_score >= NEEDS_REVIEW_THRESHOLD:
        return "needs_review"
    return "escalate_required"


async def log_audit_event(
    db: AsyncSession,
    tenant_id: UUID,
    event_type: str,
    actor: str,
    content_id: Optional[UUID] = None,
    metadata_: Optional[Dict[str, Any]] = None,
) -> ApprovalEvent:
    """
    Ghi một dòng audit (approval_events).
    event_type: GENERATE_PLAN | GENERATE_CONTENT | AUTO_APPROVED | NEEDS_REVIEW | ESCALATED | APPROVED | REJECTED.
    """
    ev = ApprovalEvent(
        tenant_id=tenant_id,
        content_id=content_id,
        event_type=event_type,
        actor=actor,
        metadata_=metadata_ or {},
    )
    db.add(ev)
    await db.flush()
    return ev


async def approve_content(
    db: AsyncSession,
    tenant_id: UUID,
    content_id: UUID,
    actor: str = "HUMAN",
    approved_by: Optional[str] = None,
) -> ContentItem:
    """
    Duyệt nội dung: set status=approved, review_state=approved, approved_at=now, approved_by.
    Ghi event APPROVED. Trả về content item đã cập nhật.
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
    if item.status == "approved":
        raise ValueError("already_approved")
    if item.review_state == "rejected":
        raise ValueError("cannot_approve_rejected")

    now = datetime.now(timezone.utc)
    item.status = "approved"
    item.review_state = "approved"
    item.approved_at = now
    item.rejected_at = None
    item.rejection_reason = None
    item.rejected_by = None
    if approved_by is not None:
        item.approved_by = approved_by
    await db.flush()

    await log_audit_event(
        db,
        tenant_id=tenant_id,
        content_id=content_id,
        event_type="APPROVED",
        actor=actor,
        metadata_={"approved_at": now.isoformat(), "approved_by": approved_by},
    )
    logger.info("approval.approved", content_id=str(content_id), tenant_id=str(tenant_id), actor=actor)
    return item


async def reject_content(
    db: AsyncSession,
    tenant_id: UUID,
    content_id: UUID,
    reason: str,
    actor: str = "HUMAN",
    rejected_by: Optional[str] = None,
) -> ContentItem:
    """
    Từ chối nội dung: set status=rejected, review_state=rejected, rejected_at=now, rejection_reason, rejected_by.
    Ghi event REJECTED kèm reason.
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

    now = datetime.now(timezone.utc)
    item.status = "rejected"
    item.review_state = "rejected"
    item.rejected_at = now
    item.rejection_reason = reason
    if rejected_by is not None:
        item.rejected_by = rejected_by
    await db.flush()

    await log_audit_event(
        db,
        tenant_id=tenant_id,
        content_id=content_id,
        event_type="REJECTED",
        actor=actor,
        metadata_={"reason": reason, "rejected_at": now.isoformat(), "rejected_by": rejected_by},
    )
    logger.info("approval.rejected", content_id=str(content_id), tenant_id=str(tenant_id), actor=actor)
    return item


async def list_audit_events(
    db: AsyncSession,
    tenant_id: UUID,
    limit: int = 50,
) -> List[ApprovalEvent]:
    """Lấy danh sách audit events của tenant, mới nhất trước."""
    q = (
        select(ApprovalEvent)
        .where(ApprovalEvent.tenant_id == tenant_id)
        .order_by(ApprovalEvent.created_at.desc())
        .limit(limit)
    )
    r = await db.execute(q)
    return list(r.scalars().all())
