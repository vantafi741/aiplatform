"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.logging_config import configure_logging, get_logger
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.routers import (
    api_health_router,
    health_router,
    onboarding_router,
    planner_router,
    plans_router,
    content_router,
    content_items_router,
    publish_router,
    audit_router,
    scheduler_router,
    kpi_router,
    kb_router,
    revenue_mv1_router,
    revenue_mv2_router,
    gdrive_assets_router,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown: logging, scheduler worker, teardown."""
    configure_logging()
    logger.info("app_started", version=__version__)
    from app.services.scheduler_service import start_scheduler, stop_scheduler
    await start_scheduler(app)
    yield
    await stop_scheduler()
    logger.info("app_shutdown")


app = FastAPI(
    title="AI Content Director",
    version=__version__,
    lifespan=lifespan,
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CorrelationIdMiddleware)

app.include_router(api_health_router)
app.include_router(revenue_mv1_router)
app.include_router(revenue_mv2_router)
app.include_router(health_router)
app.include_router(onboarding_router)
app.include_router(planner_router)
app.include_router(plans_router)
app.include_router(content_router)
app.include_router(content_items_router)
app.include_router(publish_router)
app.include_router(audit_router)
app.include_router(scheduler_router)
app.include_router(kpi_router)
app.include_router(kb_router)
app.include_router(gdrive_assets_router)


@app.get("/")
def root() -> dict[str, str]:
    """Root endpoint: app name and version."""
    return {"name": "ai_content_director", "version": __version__}
