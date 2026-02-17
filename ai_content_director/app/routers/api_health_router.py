# Foundation health: /api/healthz (liveness), /api/readyz (readiness). readyz check DB + Redis.
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.config import get_settings
from app.logging_config import get_logger

router = APIRouter(prefix="/api", tags=["health"])
logger = get_logger(__name__)


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness: process dang chay. Luon 200."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)):
    """Readiness: DB va Redis (neu co) san sang. 200 OK, 503 neu loi."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.warning("readyz.db_fail", error=str(e))
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "db": "fail"},
        )

    settings = get_settings()
    if settings.redis_url:
        try:
            from redis.asyncio import Redis
            client = Redis.from_url(settings.redis_url, decode_responses=True)
            await client.ping()
            await client.aclose()
        except Exception as e:
            logger.warning("readyz.redis_fail", error=str(e))
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "redis": "fail"},
            )

    return {"status": "ok", "db": "ok", "redis": "ok"}
