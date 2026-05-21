"""Simulation GET endpoint — thin HTTP adapter over the canonical shared operation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.simulation.get import get_simulation_impl
from app.infra.simulation.group import group_simulation_impl
from app.infra.simulation.types import (
    GetSimulationApiRequest,
    GetSimulationApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()
SECTIONS = (
    "names",
    "descriptions",
    "flags",
    "departments",
    "scenarios",
    "scenario_flags",
    "scenario_positions",
    "scenario_rubrics",
    "scenario_time_limits",
)


@router.post("/get", response_model=GetSimulationApiResponse)
async def get_simulation(
    request: GetSimulationApiRequest,
    http_request: Request,
    response: Response,
) -> GetSimulationApiResponse:
    """Get simulation information using the canonical shared simulation operation."""
    bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

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
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> GetSimulationApiResponse:
            return await get_simulation_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                id=request.id or request.simulation_id,
                draft_id=request.draft_id,
                filters={section: getattr(request, section) for section in SECTIONS},
                scenario_search=request.scenario_search,
                scenario_show_selected=request.scenario_show_selected,
                filter_scenario_ids=request.filter_scenario_ids,
                bypass_cache=bypass_cache,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="simulation",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            draft_id=request.draft_id,
            operation="get",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=GetSimulationApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Cache-Tags"] = "simulations"
        response.headers["X-Cache-Hit"] = "0"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="get_simulation",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
