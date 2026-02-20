"""
AI Lead System: classify intent từ text (rule-first; LLM optional khi unknown).
Trả về intent_label, priority, confidence_score. HITL: >=0.85 auto, 0.70-0.85 draft, <0.70 escalate.
"""
import asyncio
import re
from dataclasses import dataclass
from typing import Optional

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# Ngưỡng HITL (theo task)
AUTO_THRESHOLD = 0.85
DRAFT_THRESHOLD = 0.70


@dataclass
class ClassifyResult:
    """Kết quả classify: intent, priority, confidence."""
    intent_label: str
    priority: str  # high | medium | low
    confidence_score: float


# Rule-first: từ khóa -> (intent_label, priority, confidence)
# priority high = cần follow-up nhanh (sẽ gọi n8n webhook)
INTENT_RULES: list[tuple[list[str], tuple[str, str, float]]] = [
    # (keywords, (intent_label, priority, confidence))
    (["giá", "bao nhiêu", "báo giá", "quote", "pricing", "chi phí", "phí"], ("inquiry_price", "high", 0.88)),
    (["mua", "đặt hàng", "order", "mua hàng", "mua ngay"], ("purchase_intent", "high", 0.90)),
    (["liên hệ", "contact", "tư vấn", "tư vấn miễn phí", "gọi lại"], ("contact_request", "high", 0.87)),
    (["demo", "xem thử", "dùng thử", "trial"], ("demo_request", "high", 0.89)),
    (["khiếu nại", "phàn nàn", "complaint", "lỗi", "sai"], ("complaint", "high", 0.92)),
    (["cảm ơn", "thanks", "thank you", "tốt quá"], ("thanks", "low", 0.91)),
    (["hay", "thích", "like", "tuyệt"], ("engagement", "low", 0.85)),
    (["? ", "?", "gì", "như thế nào", "how", "what", "when"], ("inquiry", "medium", 0.78)),
]


def _normalize(text: Optional[str]) -> str:
    """Chuẩn hóa text để so khớp rule: lowercase, strip."""
    if not text or not isinstance(text, str):
        return ""
    return text.lower().strip()


def classify_by_rules(text: Optional[str]) -> Optional[ClassifyResult]:
    """
    Classify theo rule: tìm từ khóa trong text.
    Trả về ClassifyResult nếu match, None nếu unknown.
    """
    normalized = _normalize(text)
    if not normalized:
        return ClassifyResult(intent_label="unknown", priority="low", confidence_score=0.5)

    for keywords, (intent_label, priority, confidence) in INTENT_RULES:
        for kw in keywords:
            if kw in normalized:
                logger.debug("lead_classify.rule_matched", keyword=kw, intent=intent_label, priority=priority)
                return ClassifyResult(intent_label=intent_label, priority=priority, confidence_score=confidence)

    return None


async def classify_with_llm(text: Optional[str]) -> ClassifyResult:
    """
    Gọi LLM để classify khi rule không match (unknown).
    asyncio.wait_for(timeout=settings.lead_classify_llm_timeout_seconds).
    On TimeoutError/Exception => fallback intent=unknown, priority=medium, confidence=0.5.
    """
    from app.services.llm_service import LLMService

    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning("lead_classify.llm_skipped", reason="no_openai_api_key")
        return ClassifyResult(intent_label="unknown", priority="medium", confidence_score=0.5)

    llm = LLMService(settings)
    timeout_sec = settings.lead_classify_llm_timeout_seconds
    timeout_sec = max(3, min(60, timeout_sec))
    prompt = f"""Phân loại ý định (intent) của khách hàng từ tin nhắn sau. Trả về JSON duy nhất với keys: intent_label, priority, confidence_score.
- intent_label: một trong [inquiry, inquiry_price, purchase_intent, contact_request, demo_request, complaint, thanks, engagement, unknown]
- priority: high (cần follow-up), medium, low
- confidence_score: số thực 0.0-1.0

Tin nhắn: "{text or '(trống)'}"

Chỉ trả về JSON, không giải thích. Ví dụ: {{"intent_label": "inquiry", "priority": "medium", "confidence_score": 0.75}}
"""
    fallback = ClassifyResult(intent_label="unknown", priority="low", confidence_score=0.5)

    async def _call_llm() -> ClassifyResult:
        import json
        client = llm._get_client()
        if not client:
            return fallback

        def _sync_create():
            return client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=150,
            )

        resp = await asyncio.to_thread(_sync_create)
        content = (resp.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = re.sub(r"^```\w*\n?", "", content).rstrip("`")
        data = json.loads(content)
        intent_label = str(data.get("intent_label", "unknown"))[:64]
        priority = str(data.get("priority", "low")).lower()
        if priority not in ("high", "medium", "low"):
            priority = "low"
        confidence = float(data.get("confidence_score", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        logger.info("lead_classify.llm_done", intent=intent_label, priority=priority, confidence=confidence)
        return ClassifyResult(intent_label=intent_label, priority=priority, confidence_score=confidence)

    try:
        return await asyncio.wait_for(_call_llm(), timeout=float(timeout_sec))
    except asyncio.TimeoutError:
        logger.warning("lead_classify.llm_timeout", timeout_sec=timeout_sec)
        return fallback
    except Exception as e:
        logger.warning("lead_classify.llm_failed", error=str(e))
        return fallback


async def classify_intent(text: Optional[str]) -> ClassifyResult:
    """
    Classify intent: rule-first; nếu unknown và LEAD_CLASSIFY_USE_LLM=true thì gọi LLM.
    Trả về ClassifyResult (intent_label, priority, confidence_score).
    """
    result = classify_by_rules(text)
    if result is not None and result.intent_label != "unknown":
        return result

    settings = get_settings()
    if result is None:
        result = ClassifyResult(intent_label="unknown", priority="medium", confidence_score=0.5)

    if settings.lead_classify_use_llm and (text or "").strip():
        return await classify_with_llm(text)

    return result
