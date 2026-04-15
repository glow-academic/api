"""System operational router — session, group, health, activity, pricing."""

from fastapi import APIRouter

from app.routes.system.activity import router as activity_router
from app.routes.system.group import router as group_router
from app.routes.system.health import router as health_router
from app.routes.system.pricing import router as pricing_router
from app.routes.system.session import router as session_router

router = APIRouter(prefix="/system", tags=["system"])

# Absorbed sub-routers (one-to-one nesting)
router.include_router(session_router)    # prefix="/session"
router.include_router(group_router)      # prefix="/group"
router.include_router(health_router)     # prefix="/health"
router.include_router(activity_router)   # prefix="/activity"
router.include_router(pricing_router)    # prefix="/pricing"
