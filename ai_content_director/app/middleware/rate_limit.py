"""
Rate limit middleware: Redis sliding window, key theo X-Tenant-ID hoặc X-API-Key.
Default 60 req/min/tenant. Khi không có REDIS_URL thì bỏ qua (không block).
"""
import time
import uuid
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

REDIS_KEY_PREFIX = "rl:"
WINDOW_SECONDS = 60


def _rate_limit_key(request: Request) -> Optional[str]:
    """Lấy key cho rate limit: X-Tenant-ID hoặc X-API-Key (nếu có)."""
    tenant = request.headers.get("X-Tenant-ID", "").strip()
    if tenant:
        return f"tenant:{tenant}"
    api_key = request.headers.get("X-API-Key", "").strip()
    if api_key:
        return f"key:{api_key[:32]}"
    return None


async def _check_sliding_window(redis_url: str, key: str, limit: int) -> bool:
    """
    Sliding window: ZADD now, ZREMRANGEBYSCORE -inf (now-60), ZCARD.
    Returns True nếu cho phép request (dưới limit), False nếu vượt.
    """
    try:
        from redis.asyncio import Redis
    except ImportError:
        logger.warning("rate_limit.redis_not_installed")
        return True
    now = time.time()
    rkey = REDIS_KEY_PREFIX + key
    try:
        client = Redis.from_url(redis_url, decode_responses=True)
        try:
            pipe = client.pipeline()
            pipe.zadd(rkey, {str(uuid.uuid4()): now})
            pipe.zremrangebyscore(rkey, "-inf", now - WINDOW_SECONDS)
            pipe.zcard(rkey)
            pipe.expire(rkey, WINDOW_SECONDS + 10)
            results = await pipe.execute()
            count = results[2] if len(results) > 2 else 0
            return count <= limit
        finally:
            await client.aclose()
    except Exception as e:
        logger.warning("rate_limit.redis_error", key=key, error=str(e))
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware: rate limit theo tenant_id hoặc api_key header (Redis sliding window)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        if not settings.redis_url:
            return await call_next(request)
        key = _rate_limit_key(request)
        if not key:
            return await call_next(request)
        limit = settings.rate_limit_per_min
        allowed = await _check_sliding_window(settings.redis_url, key, limit)
        if not allowed:
            logger.info("rate_limit.exceeded", key=key, limit=limit)
            return Response(
                content='{"detail":"Rate limit exceeded (per tenant/key)."}',
                status_code=429,
                media_type="application/json",
            )
        return await call_next(request)
