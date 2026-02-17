"""
Redis cache placeholder: get/set/delete. Dung cho foundation stack.
Khi khong co REDIS_URL thi no-op (tra None get, set/delete khong lam gi).
Rate limit van dung Redis trong middleware; module nay la placeholder cho cache dung chung.
"""
from typing import Any, Optional

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

CACHE_PREFIX = "cache:"
DEFAULT_TTL_SECONDS = 300


async def cache_get(key: str) -> Optional[str]:
    """Lay gia tri tu cache. Tra None neu khong co REDIS_URL hoac key khong ton tai."""
    settings = get_settings()
    if not settings.redis_url:
        return None
    try:
        from redis.asyncio import Redis
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            return await client.get(CACHE_PREFIX + key)
        finally:
            await client.aclose()
    except Exception as e:
        logger.warning("cache_get.error", key=key, error=str(e))
        return None


async def cache_set(key: str, value: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> bool:
    """Luu vao cache. Tra False neu khong co REDIS_URL hoac loi."""
    settings = get_settings()
    if not settings.redis_url:
        return False
    try:
        from redis.asyncio import Redis
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await client.setex(CACHE_PREFIX + key, ttl_seconds, value)
            return True
        finally:
            await client.aclose()
    except Exception as e:
        logger.warning("cache_set.error", key=key, error=str(e))
        return False


async def cache_delete(key: str) -> bool:
    """Xoa key khoi cache. Tra False neu khong co REDIS_URL hoac loi."""
    settings = get_settings()
    if not settings.redis_url:
        return False
    try:
        from redis.asyncio import Redis
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        try:
            await client.delete(CACHE_PREFIX + key)
            return True
        finally:
            await client.aclose()
    except Exception as e:
        logger.warning("cache_delete.error", key=key, error=str(e))
        return False
