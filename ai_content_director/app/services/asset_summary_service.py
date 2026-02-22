"""Service tạo/lấy asset summary từ content_assets."""
import asyncio
import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging_config import get_logger
from app.models import AssetSummary, ContentAsset
from app.services.ai_usage_service import log_usage

logger = get_logger(__name__)


def _extract_usage(resp: Any) -> Dict[str, int]:
    """Lấy usage token từ OpenAI response."""
    usage = getattr(resp, "usage", None)
    if not usage:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }


def _safe_confidence(value: Any) -> float:
    """Chuẩn hóa confidence về [0.0, 1.0]."""
    try:
        c = float(value)
    except (TypeError, ValueError):
        c = 0.6
    return max(0.0, min(1.0, c))


def _strip_markdown_json(content: str) -> str:
    """Bỏ code fence nếu model trả JSON trong markdown."""
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if len(lines) >= 3 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
        return "\n".join(lines[1:]).strip()
    return text


def _resolve_source(asset: ContentAsset) -> Tuple[str, Optional[str]]:
    """Ưu tiên local_path nếu file tồn tại, fallback storage_url."""
    local_path = (asset.local_path or "").strip()
    if local_path and Path(local_path).is_file():
        guessed_mime, _ = mimetypes.guess_type(local_path)
        return local_path, guessed_mime or asset.mime_type
    return asset.storage_url, asset.mime_type


def _fallback_summary(asset: ContentAsset, source_uri: str) -> Dict[str, Any]:
    """Fallback template khi không có OpenAI hoặc call lỗi."""
    file_name = asset.file_name or source_uri.split("/")[-1] or "asset"
    media_hint = "video" if (asset.asset_type or "").lower() == "video" else "image"
    summary = (
        f"Tài sản media ({media_hint}) '{file_name}' đã được nhận diện. "
        "Cần viết nội dung bám theo ngữ cảnh hình ảnh/video thực tế trước khi tạo caption."
    )
    return {
        "summary": summary,
        "detected_text": "",
        "objects_json": {"objects": []},
        "insights_json": {
            "key_points": ["Mô tả ngắn nội dung media", "Đề xuất góc khai thác an toàn"],
            "source_uri": source_uri,
        },
        "suggested_angle": "Nhấn mạnh thông tin nổi bật quan sát được từ media.",
        "suggested_tone": "professional",
        "confidence_score": 0.55,
        "model": "template_fallback",
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _to_data_url(local_path: str, mime_type: Optional[str]) -> Optional[str]:
    """Convert local image path thành data URL để gửi vision API."""
    path = Path(local_path)
    if not path.is_file():
        return None
    resolved_mime = mime_type or mimetypes.guess_type(local_path)[0] or "image/jpeg"
    if not resolved_mime.startswith("image/"):
        return None
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{resolved_mime};base64,{b64}"


async def _generate_summary_with_openai(
    *,
    tenant_id: UUID,
    asset: ContentAsset,
    source_uri: str,
    mime_type: Optional[str],
) -> Dict[str, Any]:
    """Gọi OpenAI Vision/LLM để tóm tắt media."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("openai_not_configured")

    from openai import OpenAI

    model = settings.openai_vision_model or settings.openai_model
    client = OpenAI(
        api_key=settings.openai_api_key,
        timeout=float(settings.openai_timeout_seconds),
        max_retries=settings.openai_max_retries,
    )

    system_prompt = (
        "Bạn là chuyên gia phân tích media cho content marketing B2B. "
        "Trả về JSON thuần với schema: "
        "{"
        "\"summary\":\"...\","
        "\"detected_text\":\"...\","
        "\"objects_json\":{\"objects\":[\"...\"]},"
        "\"insights_json\":{\"key_points\":[\"...\"],\"hooks\":[\"...\"]},"
        "\"suggested_angle\":\"...\","
        "\"suggested_tone\":\"...\","
        "\"confidence_score\":0.0"
        "}. "
        "confidence_score trong [0,1]."
    )
    user_text = (
        f"tenant_id={tenant_id}; asset_id={asset.id}; asset_type={asset.asset_type}; "
        f"mime_type={mime_type or asset.mime_type or 'unknown'}; source={source_uri}. "
        "Hãy tóm tắt media để dùng làm ngữ cảnh bắt buộc trước khi viết nội dung."
    )

    image_payload = None
    if source_uri.startswith("http://") or source_uri.startswith("https://"):
        image_payload = {"type": "image_url", "image_url": {"url": source_uri}}
    elif source_uri.startswith("data:image/"):
        image_payload = {"type": "image_url", "image_url": {"url": source_uri}}
    else:
        data_url = _to_data_url(source_uri, mime_type or asset.mime_type)
        if data_url:
            image_payload = {"type": "image_url", "image_url": {"url": data_url}}

    if image_payload:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [{"type": "text", "text": user_text}, image_payload]},
        ]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]

    resp = await asyncio.to_thread(
        client.chat.completions.create,
        model=model,
        messages=messages,
        temperature=0.2,
    )
    raw = (resp.choices[0].message.content or "").strip()
    cleaned = _strip_markdown_json(raw)
    data = json.loads(cleaned)
    usage = _extract_usage(resp)
    return {
        "summary": str(data.get("summary") or "").strip() or "No summary",
        "detected_text": str(data.get("detected_text") or "").strip(),
        "objects_json": data.get("objects_json") if isinstance(data.get("objects_json"), dict) else {},
        "insights_json": data.get("insights_json") if isinstance(data.get("insights_json"), dict) else {},
        "suggested_angle": str(data.get("suggested_angle") or "").strip(),
        "suggested_tone": str(data.get("suggested_tone") or "").strip(),
        "confidence_score": _safe_confidence(data.get("confidence_score")),
        "model": model,
        "usage": usage,
    }


async def get_or_create_asset_summary(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    asset_id: UUID,
) -> Tuple[AssetSummary, bool]:
    """
    Lấy cache asset summary nếu đã có, nếu chưa thì generate và lưu.

    Returns:
      (summary_row, cached)
    """
    existing_q = await db.execute(
        select(AssetSummary).where(
            AssetSummary.tenant_id == tenant_id,
            AssetSummary.asset_id == asset_id,
        )
    )
    existing = existing_q.scalar_one_or_none()
    if existing:
        return existing, True

    asset_q = await db.execute(
        select(ContentAsset).where(
            ContentAsset.id == asset_id,
            ContentAsset.tenant_id == tenant_id,
        )
    )
    asset = asset_q.scalar_one_or_none()
    if not asset:
        raise ValueError("asset_not_found")

    source_uri, mime_type = _resolve_source(asset)

    try:
        generated = await _generate_summary_with_openai(
            tenant_id=tenant_id,
            asset=asset,
            source_uri=source_uri,
            mime_type=mime_type,
        )
    except ValueError as err:
        if str(err) != "openai_not_configured":
            raise
        generated = _fallback_summary(asset, source_uri)
    except Exception as err:  # fallback an toàn
        logger.warning(
            "asset_summary.openai_failed",
            tenant_id=str(tenant_id),
            asset_id=str(asset_id),
            error=str(err),
        )
        generated = _fallback_summary(asset, source_uri)

    row = AssetSummary(
        tenant_id=tenant_id,
        asset_id=asset_id,
        model=generated.get("model"),
        summary=generated.get("summary") or "No summary",
        detected_text=generated.get("detected_text"),
        objects_json=generated.get("objects_json"),
        insights_json=generated.get("insights_json"),
        suggested_angle=generated.get("suggested_angle"),
        suggested_tone=generated.get("suggested_tone"),
        confidence_score=_safe_confidence(generated.get("confidence_score")),
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        re_q = await db.execute(
            select(AssetSummary).where(
                AssetSummary.tenant_id == tenant_id,
                AssetSummary.asset_id == asset_id,
            )
        )
        raced = re_q.scalar_one_or_none()
        if raced:
            return raced, True
        raise

    usage = generated.get("usage") or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    try:
        await log_usage(
            db=db,
            tenant_id=tenant_id,
            feature="MEDIA_SUMMARY",
            model=row.model or "template_fallback",
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            total_tokens=int(usage.get("total_tokens", 0)),
        )
    except Exception as err:
        logger.warning(
            "asset_summary.log_usage_failed",
            tenant_id=str(tenant_id),
            asset_id=str(asset_id),
            error=str(err),
        )

    logger.info(
        "asset_summary.generated",
        tenant_id=str(tenant_id),
        asset_id=str(asset_id),
        summary_id=str(row.id),
        model=row.model or "template_fallback",
    )
    return row, False
