"""Simulation drafts list endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.simulation.drafts.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.simulation.drafts import list_simulation_drafts_impl
from app.infra.simulation.group import group_simulation_impl
from app.infra.simulation.types import (
    GetSimulationDraftsApiRequest,
    GetSimulationDraftsApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/drafts", response_model=GetSimulationDraftsApiResponse)
async def get_simulation_drafts(
    request: GetSimulationDraftsApiRequest,
    http_request: Request,
    response: Response,
) -> GetSimulationDraftsApiResponse:
    """List simulation drafts owned by the current profile."""
    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        session_id = http_request.state.session_id
        pool = get_pool()
        redis = get_redis_client()
        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_simulation_impl(
                pool, redis, profile_id=UUID(profile_id), session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> GetSimulationDraftsApiResponse:
            return await list_simulation_drafts_impl(
                pool,
                redis,
                profile_id=UUID(profile_id),
                session_id=session_id,
                search=request.search,
                date_from=request.date_from,
                date_to=request.date_to,
                page_limit=request.page_limit,
                page_offset=request.page_offset,
                bypass_cache=bypass_cache,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="simulation",
            profile_id=UUID(profile_id),
            session_id=session_id,
            group_id=group_id,
            operation="drafts",
            arguments={},
            bypass_cache=bypass_cache,
            response_model=GetSimulationDraftsApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
        response.headers["X-Cache-Tags"] = "simulations,drafts"
        return result

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="get_simulation_drafts",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
