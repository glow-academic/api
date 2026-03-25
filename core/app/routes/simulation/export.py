"""Simulation export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.globals import get_pool, get_redis_client
from app.infra.simulation.export import export_simulation_impl
from app.infra.simulation.types import (
    ExportSimulationApiRequest,
    ExportSimulationApiResponse,
)

router = APIRouter()


@router.post("/export", response_model=ExportSimulationApiResponse)
async def export_simulations(
    body: ExportSimulationApiRequest,
    http_request: Request,
) -> ExportSimulationApiResponse:
    """Export all simulations as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_simulation_impl(
        pool,
        redis,
        profile_id=profile_id,
        simulation_id=body.simulation_id,
    )
