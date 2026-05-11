"""System operational router — context, generate, generations, group, problem + child sub-routers + media."""

from fastapi import APIRouter

# Child sub-routers (VIEW artifacts absorbed into system)
from app.routes.system.activity import router as activity_router

# Media operations (promoted from group to system level)
from app.routes.system.audio import router as audio_router
from app.routes.system.call import router as call_router

# Top-level system operations
from app.routes.system.context import router as context_router
from app.routes.system.export import router as export_router
from app.routes.system.file import router as file_router
from app.routes.system.generate import router as generate_router
from app.routes.system.generations import router as generations_router
from app.routes.system.group import router as group_router
from app.routes.system.health import router as health_router
from app.routes.system.image import router as image_router
from app.routes.system.pricing import router as pricing_router
from app.routes.system.problem import router as problem_router
from app.routes.system.refresh import router as refresh_router
from app.routes.system.session import router as session_router
from app.routes.system.text import router as text_router
from app.routes.system.video import router as video_router

router = APIRouter(prefix="/system", tags=["system"])

# Top-level system operations
router.include_router(context_router)
router.include_router(export_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(problem_router)
router.include_router(refresh_router)

# Child sub-routers
router.include_router(group_router)      # prefix="/group"
router.include_router(session_router)    # prefix="/session"
router.include_router(health_router)     # prefix="/health"
router.include_router(activity_router)   # prefix="/activity"
router.include_router(pricing_router)    # prefix="/pricing"

# Media operations (system-level, not nested under group)
router.include_router(audio_router)      # prefix="/audio"
router.include_router(call_router)       # prefix="/call"
router.include_router(file_router)       # prefix="/file"
router.include_router(image_router)      # prefix="/image"
router.include_router(text_router)       # prefix="/text"
router.include_router(video_router)      # prefix="/video"
