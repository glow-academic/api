"""V5 API router — flat URL hierarchy under /v5.

All artifact endpoints mount directly (no /artifacts intermediary).
Event delivery is SSE-only at /v5/stream with schema at /v5/stream/schema/*.
"""
# mypy: ignore-errors

from fastapi import APIRouter, Depends

from app.infra.identity.middleware import require_auth
from app.routes.v5.activity import router as activity_artifact_router
from app.routes.v5.activity.problem import router as problem_router
from app.routes.v5.agent import router as agents_router
from app.routes.v5.attempt import router as attempt_artifact_router
from app.routes.v5.auth import router as auth_router
from app.routes.v5.benchmark import router as benchmark_artifact_router
from app.routes.v5.chat import router as chat_artifact_router
from app.routes.v5.cohort import router as cohorts_router
from app.routes.v5.connect import router as connect_router
from app.routes.v5.context import router as context_router
from app.routes.v5.dashboard import router as dashboard_artifact_router
from app.routes.v5.department import router as departments_router
from app.routes.v5.disconnect import router as disconnect_router
from app.routes.v5.docs import router as docs_router
from app.routes.v5.document import router as documents_router
from app.routes.v5.emulate import router as emulate_router
from app.routes.v5.eval import router as evals_router
from app.routes.v5.field import router as fields_router
from app.routes.v5.generate import router as generate_router
from app.routes.v5.group import router as group_router
from app.routes.v5.health import router as health_artifact_router
from app.routes.v5.home import router as home_artifact_router
from app.routes.v5.leaderboard import router as leaderboard_artifact_router
from app.routes.v5.model import router as models_router
from app.routes.v5.parameter import router as parameters_router
from app.routes.v5.persona import router as personas_router
from app.routes.v5.practice import router as practice_artifact_router
from app.routes.v5.pricing import router as pricing_artifact_router
from app.routes.v5.profile import router as profile_router
from app.routes.v5.provider import router as providers_router
from app.routes.v5.record import router as record_artifact_router
from app.routes.v5.reports import router as reports_artifact_router
from app.routes.v5.rubric import router as rubrics_router
from app.routes.v5.scenario import router as scenarios_router
from app.routes.v5.session import router as session_router
from app.routes.v5.setting import router as settings_router
from app.routes.v5.simulation import router as simulations_router
from app.routes.v5.test import router as test_artifact_router
from app.routes.v5.tool import router as tools_router
from app.routes.v5.unemulate import router as unemulate_router
# ============================================================================
# Main Router — /v5
# ============================================================================
router: APIRouter = APIRouter(
    prefix="/v5",
    tags=["v5"],
    dependencies=[
        Depends(require_auth),
    ],
)

# ============================================================================
# Artifacts — directly under /v5 (no /artifacts prefix)
# ============================================================================
# Core content artifacts
router.include_router(personas_router)
router.include_router(scenarios_router)
router.include_router(simulations_router)
router.include_router(documents_router)
router.include_router(departments_router)
router.include_router(cohorts_router)
router.include_router(evals_router)
router.include_router(rubrics_router)
router.include_router(settings_router)
router.include_router(agents_router)
router.include_router(models_router)
router.include_router(providers_router)
router.include_router(parameters_router)
router.include_router(fields_router)
router.include_router(profile_router)
router.include_router(auth_router)
router.include_router(tools_router)
router.include_router(group_router)
router.include_router(session_router)
router.include_router(chat_artifact_router)
router.include_router(home_artifact_router)
router.include_router(practice_artifact_router)
router.include_router(attempt_artifact_router)

# View-based artifacts
router.include_router(record_artifact_router)
router.include_router(dashboard_artifact_router)
router.include_router(reports_artifact_router)
router.include_router(leaderboard_artifact_router)
router.include_router(pricing_artifact_router)
router.include_router(activity_artifact_router)
router.include_router(health_artifact_router)
router.include_router(benchmark_artifact_router)
router.include_router(test_artifact_router)

# ============================================================================
# Root-level actions — /v5/connect, /v5/disconnect, /v5/context, /v5/generate
# ============================================================================
router.include_router(connect_router)
router.include_router(disconnect_router)
router.include_router(context_router)
router.include_router(problem_router)
router.include_router(emulate_router)
router.include_router(unemulate_router)
router.include_router(generate_router)

# ============================================================================
# Docs — /v5/docs
# ============================================================================
router.include_router(docs_router)
