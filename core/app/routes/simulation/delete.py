"""Simulation delete endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.simulation.delete.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.simulation.delete import delete_simulation_impl
from app.infra.simulation.group import group_simulation_impl
from app.infra.simulation.types import (
    DeleteSimulationApiRequest,
    DeleteSimulationApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/delete", response_model=DeleteSimulationApiResponse)
async def delete_simulation(
    request: DeleteSimulationApiRequest,
    http_request: Request,
    response: Response,
) -> DeleteSimulationApiResponse:
    """Bulk delete simulations — composable infra architecture."""
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

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_simulation_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        is_ack = request.accept is not None and request.idempotency_key is not None
        premint_call_id = None if is_ack else request.idempotency_key

        async def _runner() -> DeleteSimulationApiResponse:
            return await delete_simulation_impl(
                pool,
                redis,
                profile_id=profile_id,
                ids=request.simulation_ids,
                session_id=session_id,
                idempotency_key=request.idempotency_key,
                accept=request.accept if request.idempotency_key else None,
                soft=request.soft,
                # All-matching path
                all=bool(request.all),
                excluded_ids=request.excluded_ids,
                search=request.search,
                filter_scenario_ids=request.filter_scenario_ids,
                filter_cohort_ids=request.filter_cohort_ids,
                filter_department_ids=request.filter_department_ids,
                scenario_search=request.scenario_search,
                cohort_search=request.cohort_search,
                department_search=request.department_search,
                flag_search=request.flag_search,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="simulation",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="delete",
            arguments=request.model_dump(mode="json"),
            response_model=DeleteSimulationApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.idempotency_key,  # idempotency replay gate
            call_id=premint_call_id,  # pre-mint calls_entry with client key (HTTP soft FK)
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="delete_simulation",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
