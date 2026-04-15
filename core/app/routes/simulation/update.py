"""Simulation update endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.simulation.update.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.simulation.group import group_simulation_impl
from app.infra.simulation.update import update_simulation_impl
from app.infra.simulation.types import (
    UpdateSimulationApiRequest,
    UpdateSimulationApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/update", response_model=UpdateSimulationApiResponse)
async def update_simulation(
    request: UpdateSimulationApiRequest,
    http_request: Request,
    response: Response,
) -> UpdateSimulationApiResponse:
    """Update simulations using composable infra architecture."""
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

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_simulation_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> UpdateSimulationApiResponse:
            return await update_simulation_impl(
                pool,
                redis,
                profile_id=profile_id,
                request=request,
                session_id=session_id,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="simulation",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="update",
            arguments=request.model_dump(mode="json"),
            response_model=UpdateSimulationApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "simulations"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="update_simulation",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
