"""Scenario export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.globals import get_pool, get_redis_client
from app.infra.scenario.export import export_scenario_impl
from app.infra.scenario.types import (
    ExportScenarioApiRequest,
    ExportScenarioApiResponse,
)

router = APIRouter()


@router.post("/export", response_model=ExportScenarioApiResponse)
async def export_scenarios(
    body: ExportScenarioApiRequest,
    http_request: Request,
) -> ExportScenarioApiResponse:
    """Export all scenarios as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_scenario_impl(
        pool,
        redis,
        profile_id=profile_id,
        scenario_id=body.scenario_id,
    )
