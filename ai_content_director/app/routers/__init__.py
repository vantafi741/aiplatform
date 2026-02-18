"""API routers."""
from app.routers.api_health_router import router as api_health_router
from app.routers.health_router import router as health_router
from app.routers.onboarding_router import router as onboarding_router
from app.routers.planner_router import router as planner_router
from app.routers.content_router import router as content_router
from app.routers.publish_router import router as publish_router
from app.routers.audit_router import router as audit_router
from app.routers.scheduler_router import router as scheduler_router
from app.routers.kpi_router import router as kpi_router
from app.routers.kb_router import router as kb_router
from app.routers.revenue_mv1_router import router as revenue_mv1_router
from app.routers.revenue_mv2_router import router as revenue_mv2_router
from app.routers.gdrive_assets_router import router as gdrive_assets_router

__all__ = [
    "api_health_router",
    "health_router",
    "onboarding_router",
    "planner_router",
    "content_router",
    "publish_router",
    "audit_router",
    "scheduler_router",
    "kpi_router",
    "kb_router",
    "revenue_mv1_router",
    "revenue_mv2_router",
    "gdrive_assets_router",
]
