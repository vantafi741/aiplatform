"""
Webhook nhận event Facebook (comment/inbox) -> lead_signals.
POST /webhooks/facebook. tenant_id: ưu tiên header X-Tenant-ID, fallback body. Log tenant_id_source.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.logging_config import get_logger
from app.services.lead_service import process_facebook_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = get_logger(__name__)


@router.post("/facebook")
async def facebook_webhook(
    request: Request,
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Nhận webhook từ Facebook (comment/inbox). Parse entry[] (mock + messaging/comment thật),
    dedup theo external_message_id, classify -> lead_signals, audit, n8n khi priority=high.
    Tenant: ưu tiên X-Tenant-ID (header), fallback body.tenant_id.
    """
    try:
        body = await request.json()
    except Exception as e:
        logger.warning("webhook.facebook.invalid_body", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Ưu tiên header X-Tenant-ID, fallback body.tenant_id
    tenant_id_raw = x_tenant_id or body.get("tenant_id")
    tenant_id_source = "header" if x_tenant_id else "body"
    if not tenant_id_raw:
        logger.warning("webhook.facebook.missing_tenant")
        raise HTTPException(status_code=400, detail="tenant_id required (X-Tenant-ID header or body)")

    try:
        tenant_id = UUID(str(tenant_id_raw).strip()) if isinstance(tenant_id_raw, str) else tenant_id_raw
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid tenant_id")

    logger.info(
        "webhook.facebook.received",
        tenant_id=str(tenant_id),
        tenant_id_source=tenant_id_source,
        object=body.get("object"),
    )

    created_ids = await process_facebook_webhook(db, tenant_id, body)
    return {"ok": True, "created": len(created_ids), "lead_ids": [str(i) for i in created_ids]}
