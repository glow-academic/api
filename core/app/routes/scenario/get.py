"""Scenario GET endpoint — thin HTTP adapter over the canonical shared operation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.scenario.get import SECTIONS, get_scenario_impl
from app.infra.scenario.group import group_scenario_impl
from app.infra.scenario.types import (
    GetScenarioApiRequest,
    GetScenarioApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/get", response_model=GetScenarioApiResponse)
async def get_scenario(
    request: GetScenarioApiRequest,
    http_request: Request,
    response: Response,
) -> GetScenarioApiResponse:
    """Get scenario information using the canonical shared scenario operation."""
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
            group_result = await group_scenario_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        # Build filters dict from nested SectionFilter objects
        filters = {
            s: getattr(request, s)
            for s in SECTIONS
            if getattr(request, s) is not None
        }

        async def _runner() -> GetScenarioApiResponse:
            return await get_scenario_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                id=request.id,
                draft_id=request.draft_id,
                filters=filters,
                bypass_cache=bypass_cache,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="scenario",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            draft_id=request.draft_id,
            operation="get",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=GetScenarioApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Cache-Tags"] = "scenarios"
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
            operation="get_scenario",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
