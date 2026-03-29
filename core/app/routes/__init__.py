"""Root router — collects all top-level route modules."""
# mypy: ignore-errors

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.infra.identity.middleware import require_auth
from app.routes.activity import router as activity_artifact_router
from app.routes.activity.problem import router as problem_router
from app.routes.agent import router as agents_router
from app.routes.attempt import router as attempt_artifact_router
from app.routes.auth import router as auth_router
from app.routes.authorize import router as authorize_router
from app.routes.oidc_callback import router as oidc_callback_router
from app.routes.benchmark import router as benchmark_artifact_router
from app.routes.chat import router as chat_artifact_router
from app.routes.cohort import router as cohorts_router
from app.routes.connect import router as connect_router
from app.routes.context import router as context_router
from app.routes.dashboard import router as dashboard_artifact_router
from app.routes.department import router as departments_router
from app.routes.disconnect import router as disconnect_router
from app.routes.discovery import router as discovery_router
from app.routes.docs import router as docs_router
from app.routes.document import router as documents_router
from app.routes.emulate import router as emulate_router
from app.routes.eval import router as evals_router
from app.routes.field import router as fields_router
from app.routes.generate import router as generate_router
from app.routes.group import router as group_router
from app.routes.health import router as health_artifact_router
from app.routes.home import router as home_artifact_router
from app.routes.jwks import router as jwks_router
from app.routes.leaderboard import router as leaderboard_artifact_router
from app.routes.login import router as login_router
from app.routes.model import router as models_router
from app.routes.parameter import router as parameters_router
from app.routes.persona import router as personas_router
from app.routes.practice import router as practice_artifact_router
from app.routes.pricing import router as pricing_artifact_router
from app.routes.profile import router as profile_router
from app.routes.provider import router as providers_router
from app.routes.record import router as record_artifact_router
from app.routes.reports import router as reports_artifact_router
from app.routes.rubric import router as rubrics_router
from app.routes.scenario import router as scenarios_router
from app.routes.session import router as session_router
from app.routes.setting import router as settings_router
from app.routes.simulation import router as simulations_router
from app.routes.stream import router as stream_router
from app.routes.test import router as test_artifact_router
from app.routes.token import router as token_router
from app.routes.tool import router as tools_router
from app.routes.unemulate import router as unemulate_router
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

# Core content artifacts
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
api_router.include_router(group_router)
api_router.include_router(session_router)
api_router.include_router(chat_artifact_router)
api_router.include_router(home_artifact_router)
api_router.include_router(practice_artifact_router)
api_router.include_router(attempt_artifact_router)

# View-based artifacts
api_router.include_router(record_artifact_router)
api_router.include_router(dashboard_artifact_router)
api_router.include_router(reports_artifact_router)
api_router.include_router(leaderboard_artifact_router)
api_router.include_router(pricing_artifact_router)
api_router.include_router(activity_artifact_router)
api_router.include_router(health_artifact_router)
api_router.include_router(benchmark_artifact_router)
api_router.include_router(test_artifact_router)

# Root-level actions
api_router.include_router(connect_router)
api_router.include_router(disconnect_router)
api_router.include_router(context_router)
api_router.include_router(problem_router)
api_router.include_router(emulate_router)
api_router.include_router(unemulate_router)
api_router.include_router(generate_router)

# Docs
api_router.include_router(docs_router)

# ============================================================================
# Root Router
# ============================================================================
router = APIRouter()

router.include_router(api_router)
router.include_router(stream_router)
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
