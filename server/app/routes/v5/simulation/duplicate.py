"""Simulation duplicate endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.simulation.duplicate.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.simulation.duplicate import duplicate_simulation_impl
from app.infra.simulation.types import (
    DuplicateSimulationApiRequest,
    DuplicateSimulationApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post(
    "/duplicate",
    response_model=DuplicateSimulationApiResponse,
)
async def duplicate_simulation(
    request: DuplicateSimulationApiRequest,
    http_request: Request,
    response: Response,
) -> DuplicateSimulationApiResponse:
    """Duplicate a simulation — composable infra architecture."""
    tags = ["simulations"]

    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> DuplicateSimulationApiResponse:
            return await duplicate_simulation_impl(
                pool,
                redis,
                profile_id=profile_id,
                simulation_id=request.simulation_id,
                session_id=session_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="simulation",
            profile_id=profile_id,
            session_id=session_id,
            operation="duplicate",
            arguments=request.model_dump(mode="json"),
            response_model=DuplicateSimulationApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="duplicate_simulation",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
