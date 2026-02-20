"""
Gọi n8n webhook (ENV WEBHOOK_URL) khi lead có priority=high để tạo follow-up task.
Timeout 3–5s (ENV N8N_WEBHOOK_TIMEOUT_SECONDS), retry 1. Log lỗi, không fail request.
"""
from typing import Any, Dict
from uuid import UUID

import httpx

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# Số lần retry khi gọi webhook (retry 1 = gọi tối đa 2 lần)
N8N_WEBHOOK_RETRIES = 1


async def notify_n8n_lead_follow_up(
    lead_id: UUID,
    tenant_id: UUID,
    payload: Dict[str, Any],
) -> bool:
    """
    POST payload lên WEBHOOK_URL (n8n) khi priority=high.
    Timeout từ ENV N8N_WEBHOOK_TIMEOUT_SECONDS (mặc định 5s), retry 1 lần.
    Trả về True nếu gửi thành công, False nếu không cấu hình hoặc lỗi.
    """
    settings = get_settings()
    url = settings.webhook_n8n_url
    if not url or not url.strip():
        logger.debug("n8n_webhook.skipped", reason="WEBHOOK_URL_not_set", lead_id=str(lead_id))
        return False

    timeout = max(3.0, min(10.0, settings.n8n_webhook_timeout_seconds))
    body = {
        "lead_id": str(lead_id),
        "tenant_id": str(tenant_id),
        **payload,
    }
    last_error: str | None = None
    for attempt in range(N8N_WEBHOOK_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=body)
                if resp.status_code >= 400:
                    last_error = f"status={resp.status_code} body={resp.text[:300]}"
                    logger.warning(
                        "n8n_webhook.failed",
                        lead_id=str(lead_id),
                        attempt=attempt + 1,
                        status=resp.status_code,
                        body=resp.text[:500],
                    )
                    if attempt < N8N_WEBHOOK_RETRIES:
                        continue
                    return False
                logger.info("n8n_webhook.sent", lead_id=str(lead_id), status=resp.status_code)
                return True
        except Exception as e:
            last_error = str(e)
            logger.warning(
                "n8n_webhook.error",
                lead_id=str(lead_id),
                attempt=attempt + 1,
                error=last_error,
            )
            if attempt >= N8N_WEBHOOK_RETRIES:
                return False
    return False
