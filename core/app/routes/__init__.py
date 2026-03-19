"""Root router — collects all top-level route modules."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.routes.authorize import router as authorize_router
from app.routes.backups import router as backups_router
from app.routes.discovery import router as discovery_router
from app.routes.jwks import router as jwks_router
from app.routes.login import router as login_router
from app.routes.stream import router as stream_router
from app.routes.token import router as token_router
from app.routes.userinfo import router as userinfo_router
from app.routes.v5 import router as v5_router
from app.routes.well_known import router as well_known_router
from app.version import __version__

router = APIRouter()

router.include_router(v5_router)
router.include_router(stream_router)
router.include_router(well_known_router)
router.include_router(jwks_router)
router.include_router(discovery_router)
router.include_router(authorize_router)
router.include_router(token_router)
router.include_router(userinfo_router)
router.include_router(login_router)
router.include_router(backups_router)


@router.get("/")
async def root_info() -> JSONResponse:
    return JSONResponse(content={
        "service": "GLOW API",
        "version": __version__,
        "status": "ok",
    })
