"""Root router — collects all top-level route modules."""
# mypy: ignore-errors

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.infra.identity.middleware import require_auth
from app.routes.agent import router as agents_router
from app.routes.attempt import router as attempt_artifact_router
from app.routes.auth import router as auth_router
from app.routes.authorize import router as authorize_router
from app.routes.cohort import router as cohorts_router
from app.routes.department import router as departments_router
from app.routes.discovery import router as discovery_router
from app.routes.document import router as documents_router
from app.routes.eval import router as evals_router
from app.routes.field import router as fields_router
from app.routes.jwks import router as jwks_router
from app.routes.login import router as login_router
from app.routes.model import router as models_router
from app.routes.oidc_callback import router as oidc_callback_router
from app.routes.parameter import router as parameters_router
from app.routes.persona import router as personas_router
from app.routes.profile import router as profile_router
from app.routes.provider import router as providers_router
from app.routes.rubric import router as rubrics_router
from app.routes.scenario import router as scenarios_router
from app.routes.setting import router as settings_router
from app.routes.simulation import router as simulations_router
from app.routes.system import router as system_router
from app.routes.test import router as test_artifact_router
from app.routes.token import router as token_router
from app.routes.tool import router as tools_router
from app.routes.userinfo import router as userinfo_router
from app.routes.well_known import router as well_known_router
from app.version import __version__

# ============================================================================
# API Router — authenticated artifact endpoints at root
# ============================================================================
api_router: APIRouter = APIRouter(
    prefix="",
    dependencies=[
        Depends(require_auth),
    ],
)

# 16 canonical CRUD artifacts
api_router.include_router(personas_router)
api_router.include_router(scenarios_router)
api_router.include_router(simulations_router)
api_router.include_router(documents_router)
api_router.include_router(departments_router)
api_router.include_router(cohorts_router)
api_router.include_router(evals_router)
api_router.include_router(rubrics_router)
api_router.include_router(settings_router)
api_router.include_router(agents_router)
api_router.include_router(models_router)
api_router.include_router(providers_router)
api_router.include_router(parameters_router)
api_router.include_router(fields_router)
api_router.include_router(profile_router)
api_router.include_router(auth_router)
api_router.include_router(tools_router)

# 3 operational parents (absorb 14 satellite artifacts)
api_router.include_router(attempt_artifact_router)   # + home, practice, dashboard, leaderboard, record, report, chat draft/drafts
api_router.include_router(test_artifact_router)      # + benchmark, invocation
api_router.include_router(system_router)             # + session, group, health, activity, pricing


# ============================================================================
# Root Router
# ============================================================================
router = APIRouter()

router.include_router(api_router)
router.include_router(well_known_router)
router.include_router(jwks_router)
router.include_router(discovery_router)
router.include_router(authorize_router)
router.include_router(oidc_callback_router)
router.include_router(token_router)
router.include_router(userinfo_router)
router.include_router(login_router)


@router.get("/")
async def root_info() -> JSONResponse:
    return JSONResponse(content={
        "service": "GLOW API",
        "version": __version__,
        "status": "ok",
    })
