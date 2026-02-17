"""
OpenAI LLM service: planner and sample posts generation.
Tất cả gọi GPT nằm trong module này. Output chỉ JSON, có validate cấu trúc.
"""
import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Tuple

UsageInfo = Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens

from app.config import Settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# Planner output: {"days": [{"day_number": int, "topic": str, "content_angle": str}, ...]}
PLANNER_SCHEMA = {
    "days": [
        {"day_number": 1, "topic": "string", "content_angle": "string"},
    ]
}

# Samples output: {"posts": [{"title": str, "caption": str, "hashtags": str, "confidence_score": float}, ...]}
SAMPLES_SCHEMA = {
    "posts": [
        {"title": "string", "caption": "string", "hashtags": "string", "confidence_score": 0.0},
    ]
}


class LLMService:
    """Dịch vụ OpenAI: sinh kế hoạch nội dung và bài mẫu. Chỉ gọi GPT tại đây."""

    def __init__(self, settings: Settings) -> None:
        """Khởi tạo từ app config (OPENAI_*)."""
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.timeout_seconds = settings.openai_timeout_seconds
        self.max_retries = settings.openai_max_retries
        self.temperature = settings.openai_temperature
        self._client: Any = None

    def _get_client(self):  # noqa: ANN201
        """Lazy init OpenAI client (avoids import if key missing)."""
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key or "", timeout=float(self.timeout_seconds), max_retries=self.max_retries)
            return self._client
        except Exception as e:
            logger.warning("llm.openai_client_init_failed", error=str(e))
            return None

    def _extract_usage(self, resp: Any) -> UsageInfo:
        """Lấy prompt_tokens, completion_tokens, total_tokens từ response OpenAI."""
        usage = getattr(resp, "usage", None)
        if not usage:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        }

    async def generate_planner(self, brand_context: Dict[str, Any], days: int) -> Tuple[List[Dict[str, Any]], UsageInfo]:
        """
        Call OpenAI to generate a content plan (days 1..days).
        Returns (list of {"day_number", "topic", "content_angle"}, usage_info).
        Raises on failure or invalid JSON/structure; caller should fallback.
        """
        client = self._get_client()
        if not client or not self.api_key:
            raise ValueError("openai_not_configured")

        system = (
            "You are a content strategist for INDUSTRIAL MECHANICAL MANUFACTURING (cơ khí chế tạo, gia công, khuôn, OEM). "
            "Return ONLY valid JSON, no markdown or explanation. "
            "Strict format: {\"days\": [{\"day_number\": 1, \"topic\": \"...\", \"content_angle\": \"...\"}, ...]}. "
            "day_number must be 1 to " + str(days) + " exactly once each. topic and content_angle in Vietnamese. "
            "RULES: (1) Use industry technical vocabulary: khuôn dập, gia công CNC, phay/tiện, nhiệt luyện, dung sai, "
            "vật liệu thép/hợp kim, dây chuyền, OEM, B2B, chi tiết máy, bề mặt, ứng dụng công nghiệp. "
            "(2) NO generic marketing fluff (no 'giải pháp toàn diện', 'chất lượng hàng đầu', 'đối tác tin cậy' without proof). "
            "(3) Each content_angle must be SPECIFIC and PRACTICAL: include concrete examples (e.g. 'khuôn dập tấm 3mm', "
            "'gia công chi tiết Ø50', 'thời gian giao 2 tuần', 'vật liệu thép C45')."
        )
        industry = brand_context.get("industry", "")
        main_services = brand_context.get("main_services", [])
        brand_tone = brand_context.get("brand_tone", "")
        target = brand_context.get("target_customer", "")
        cta = brand_context.get("cta_style", "")
        user = (
            f"Industry: {industry}. Main services: {main_services}. "
            f"Brand tone: {brand_tone}. Target: {target}. CTA style (use varied phrasings): {cta}. "
            f"Generate exactly {days} days (day_number 1 to {days}), one object per day. "
            f"Each day must have a distinct, technical topic with a concrete content_angle. Return ONLY the JSON object."
        )
        start = time.perf_counter()
        try:
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=self.temperature,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            content = (resp.choices[0].message.content or "").strip()
            # Strip markdown code block if present
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            data = json.loads(content)
            days_list = data.get("days")
            if not isinstance(days_list, list) or len(days_list) != days:
                logger.warning("llm.planner_invalid_length", model=self.model, latency_ms=round(latency_ms), expected=days, got=len(days_list) if isinstance(days_list, list) else 0)
                raise ValueError("invalid_planner_output")
            seen = set()
            out = []
            for i, row in enumerate(days_list):
                if not isinstance(row, dict):
                    raise ValueError("invalid_planner_output")
                dn = row.get("day_number")
                if dn is None or not isinstance(dn, int) or dn < 1 or dn > days or dn in seen:
                    raise ValueError("invalid_planner_output")
                seen.add(dn)
                topic = (row.get("topic") or "").strip() or f"Day {dn}"
                angle = (row.get("content_angle") or "").strip()
                out.append({"day_number": dn, "topic": topic, "content_angle": angle})
            if len(out) != days:
                raise ValueError("invalid_planner_output")
            usage_info = self._extract_usage(resp)
            logger.info("llm.planner_success", model=self.model, latency_ms=round(latency_ms), days=days)
            return (out, usage_info)
        except json.JSONDecodeError as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.warning("llm.planner_json_failed", model=self.model, latency_ms=round(latency_ms), error=str(e))
            raise ValueError("invalid_planner_output") from e
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.warning("llm.planner_failed", model=self.model, latency_ms=round(latency_ms), error=str(e))
            raise

    async def generate_sample_posts(
        self,
        brand_context: Dict[str, Any],
        plan_items: List[Dict[str, Any]],
        count: int,
        kb_context: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], UsageInfo]:
        """
        Call OpenAI to generate sample posts (title, caption, hashtags, confidence_score).
        plan_items: list of {"day_number", "topic", "content_angle"}.
        kb_context: optional string from KB query (FAQ/ngữ cảnh) để inject vào prompt.
        Returns (list of posts, usage_info).
        """
        client = self._get_client()
        if not client or not self.api_key:
            raise ValueError("openai_not_configured")

        system = (
            "You are a social content writer for INDUSTRIAL MECHANICAL MANUFACTURING (cơ khí, gia công, khuôn, OEM). "
            "Return ONLY valid JSON, no markdown or explanation. "
            "Strict format: {\"posts\": [{\"title\": \"...\", \"caption\": \"...\", \"hashtags\": \"...\", \"confidence_score\": 0.0 to 1.0}, ...]}. "
            "confidence_score is your confidence in the post quality (0.0-1.0). Use Vietnamese. "
            "RULES: (1) Use technical vocabulary: khuôn dập, gia công CNC, phay/tiện, nhiệt luyện, dung sai, thép, hợp kim, "
            "chi tiết máy, OEM, B2B. (2) NO generic fluff: no 'giải pháp toàn diện' or 'chất lượng hàng đầu' without "
            "concrete examples. (3) Each caption must include at least one SPECIFIC, PRACTICAL detail (số liệu, quy trình, "
            "vật liệu, thời gian giao, ứng dụng). (4) CTA VARIATION: each post must use a DIFFERENT CTA phrasing—rotate "
            "e.g. 'Liên hệ báo giá', 'Tư vấn kỹ thuật', 'Gửi bản vẽ nhận báo giá', 'Inbox để đặt hàng'—do NOT repeat the same CTA. "
            "(5) HASHTAG STRATEGY: exactly 6 hashtags per post = 3 TECHNICAL (e.g. #khuondap #giacongcnc #thep) + "
            "2 INDUSTRY (e.g. #cokhi #sanxuat) + 1 BRAND (one consistent brand/company tag). Output hashtags as space-separated string."
        )
        industry = brand_context.get("industry", "")
        brand_tone = brand_context.get("brand_tone", "")
        cta = brand_context.get("cta_style", "")
        plan_summary = "\n".join([f"Day {p.get('day_number')}: {p.get('topic')} - {p.get('content_angle') or ''}" for p in (plan_items or [])[:count]])
        user = (
            f"Industry: {industry}. Brand tone: {brand_tone}. CTA options (use a different one per post, no repetition): {cta}. "
            f"Plan:\n{plan_summary or 'No plan'}\n\n"
        )
        if kb_context and kb_context.strip():
            user += (
                f"KB_CONTEXT (use for reference when writing captions, avoid contradicting):\n{kb_context.strip()}\n\n"
            )
        user += (
            f"Generate exactly {count} posts. Each post: title (short, technical), caption (1-2 sentences with at least one specific "
            f"detail: số liệu/quy trình/vật liệu/thời gian), hashtags (exactly 6: 3 technical + 2 industry + 1 brand, space-separated), "
            f"confidence_score (0.0-1.0). Return ONLY the JSON object."
        )
        start = time.perf_counter()
        try:
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=self.temperature,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            content = (resp.choices[0].message.content or "").strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            data = json.loads(content)
            posts = data.get("posts")
            if not isinstance(posts, list) or len(posts) != count:
                logger.warning("llm.samples_invalid_length", model=self.model, latency_ms=round(latency_ms), expected=count, got=len(posts) if isinstance(posts, list) else 0)
                raise ValueError("invalid_samples_output")
            out = []
            for row in posts:
                if not isinstance(row, dict):
                    raise ValueError("invalid_samples_output")
                title = (row.get("title") or "").strip() or "Untitled"
                caption = (row.get("caption") or "").strip()
                hashtags = (row.get("hashtags") or "").strip()
                conf = row.get("confidence_score")
                if conf is not None:
                    try:
                        conf = float(conf)
                        conf = max(0.0, min(1.0, conf))
                    except (TypeError, ValueError):
                        conf = 0.75
                else:
                    conf = 0.75
                out.append({"title": title, "caption": caption, "hashtags": hashtags, "confidence_score": conf})
            usage_info = self._extract_usage(resp)
            logger.info("llm.samples_success", model=self.model, latency_ms=round(latency_ms), count=count)
            return (out, usage_info)
        except json.JSONDecodeError as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.warning("llm.samples_json_failed", model=self.model, latency_ms=round(latency_ms), error=str(e))
            raise ValueError("invalid_samples_output") from e
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.warning("llm.samples_failed", model=self.model, latency_ms=round(latency_ms), error=str(e))
            raise

    async def generate_single_content(
        self,
        brand_context: Dict[str, Any],
        topic: str,
        content_angle: str,
    ) -> Tuple[Dict[str, Any], UsageInfo]:
        """
        Generate one content item (Revenue MVP Module 2).
        Returns ({"content_type", "title", "caption", "hashtags": list[str], "confidence_score": float}, usage_info).
        content_type: POST | REEL | CAROUSEL. hashtags: 5-30 items.
        """
        client = self._get_client()
        if not client or not self.api_key:
            raise ValueError("openai_not_configured")

        system = (
            "You are a social content writer. Return ONLY valid JSON, no markdown. "
            "Strict format: {\"content_type\": \"POST\" or \"REEL\" or \"CAROUSEL\", "
            "\"title\": \"...\", \"caption\": \"...\", \"hashtags\": [\"#a\", \"#b\", ...], \"confidence_score\": 0.0 to 1.0}. "
            "content_type must be exactly one of: POST, REEL, CAROUSEL. "
            "hashtags must be a JSON array of 5 to 30 strings (each a hashtag like #topic). "
            "Use Vietnamese for title/caption. confidence_score is your confidence in quality (0.0-1.0)."
        )
        industry = brand_context.get("industry", "")
        user = (
            f"Industry: {industry}. Topic: {topic}. Content angle: {content_angle or 'N/A'}. "
            f"Generate one content item. Return ONLY the JSON object."
        )
        start = time.perf_counter()
        try:
            resp = await asyncio.to_thread(
                client.chat.completions.create,
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=self.temperature,
            )
            latency_ms = (time.perf_counter() - start) * 1000
            content = (resp.choices[0].message.content or "").strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            data = json.loads(content)
            ctype = (data.get("content_type") or "POST").strip().upper()
            if ctype not in ("POST", "REEL", "CAROUSEL"):
                ctype = "POST"
            title = (data.get("title") or "").strip() or "Untitled"
            caption = (data.get("caption") or "").strip() or ""
            raw_hashtags = data.get("hashtags")
            if isinstance(raw_hashtags, list):
                hashtags = [str(h).strip() for h in raw_hashtags if str(h).strip()][:30]
            else:
                hashtags = ["#content", "#social", "#post", "#brand", "#industry"]
            if len(hashtags) < 5:
                hashtags = hashtags + ["#tag" + str(i) for i in range(5 - len(hashtags))]
            conf = data.get("confidence_score")
            if conf is not None:
                try:
                    conf = max(0.0, min(1.0, float(conf)))
                except (TypeError, ValueError):
                    conf = 0.75
            else:
                conf = 0.75
            usage_info = self._extract_usage(resp)
            logger.info("llm.single_content_success", model=self.model, latency_ms=round(latency_ms))
            return (
                {
                    "content_type": ctype,
                    "title": title,
                    "caption": caption,
                    "hashtags": hashtags,
                    "confidence_score": conf,
                },
                usage_info,
            )
        except json.JSONDecodeError as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.warning("llm.single_content_json_failed", model=self.model, latency_ms=round(latency_ms), error=str(e))
            raise ValueError("invalid_content_output") from e
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.warning("llm.single_content_failed", model=self.model, latency_ms=round(latency_ms), error=str(e))
            raise
