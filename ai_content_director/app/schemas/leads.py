"""
Schema cho AI Lead System: webhook Facebook, lead list API.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# --- Facebook Webhook (MVP: mock payload) ---

class FacebookWebhookEntryMessage(BaseModel):
    """Một message trong entry (comment hoặc inbox)."""
    id: Optional[str] = None
    text: Optional[str] = None
    from_: Optional[Dict[str, Any]] = Field(None, alias="from")
    created_time: Optional[str] = None

    class Config:
        populate_by_name = True


class FacebookWebhookEntry(BaseModel):
    """Một entry trong webhook (post/comments hoặc page inbox)."""
    id: Optional[str] = None
    time: Optional[int] = None
    messaging: Optional[List[Dict[str, Any]]] = None
    changes: Optional[List[Dict[str, Any]]] = None
    # Comment: post_id, comment_id, message, sender_name, sender_id, created_time
    # Cho MVP chấp nhận dict linh hoạt
    comment_id: Optional[str] = None
    post_id: Optional[str] = None
    message: Optional[str] = None
    sender_name: Optional[str] = None
    sender_id: Optional[str] = None
    created_time: Optional[str] = None
    parent_id: Optional[str] = None


class FacebookWebhookPayload(BaseModel):
    """
    Payload POST /webhooks/facebook (MVP: hỗ trợ object=page, entry[]).
    Facebook gửi object, entry[]; mỗi entry có thể là comment hoặc messaging.
    """
    object: str = "page"
    entry: List[Dict[str, Any]] = Field(default_factory=list)


# --- Lead list API ---

class LeadSignalOut(BaseModel):
    """Một lead signal trả về từ GET /api/leads."""
    id: UUID
    tenant_id: UUID
    platform: str
    source_type: str
    source_subtype: Optional[str] = None
    content_id: Optional[UUID] = None
    publish_log_id: Optional[UUID] = None
    external_post_id: Optional[str] = None
    external_thread_id: Optional[str] = None
    external_message_id: Optional[str] = None
    author_name: Optional[str] = None
    author_id: Optional[str] = None
    content_text: Optional[str] = None
    intent_label: Optional[str] = None
    priority: Optional[str] = None
    confidence_score: Optional[float] = None
    status: Optional[str] = None
    assignee: Optional[str] = None
    follow_up_at: Optional[datetime] = None
    last_contact_at: Optional[datetime] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LeadListResponse(BaseModel):
    """Response cho GET /api/leads."""
    tenant_id: UUID
    leads: List[LeadSignalOut]
    total: int
