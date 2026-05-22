"""Cohort delete endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.cohort_delete.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.cohort.delete import delete_cohort_impl
from app.infra.cohort.group import group_cohort_impl
from app.infra.cohort.types import (
    DeleteCohortApiRequest,
    DeleteCohortApiResponse,
)
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/delete", response_model=DeleteCohortApiResponse)
async def delete_cohort(
    request: DeleteCohortApiRequest,
    http_request: Request,
    response: Response,
) -> DeleteCohortApiResponse:
    """Bulk delete cohorts — composable infra architecture."""
    tags = ["cohorts"]

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
            group_result = await group_cohort_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> DeleteCohortApiResponse:
            return await delete_cohort_impl(
                pool,
                redis,
                profile_id=profile_id,
                ids=request.cohort_ids,
                session_id=session_id,
                idempotency_key=request.idempotency_key,
                accept=request.accept if request.idempotency_key else None,
                # All-matching path
                all=bool(request.all),
                excluded_ids=request.excluded_ids,
                search=request.search,
                filter_profile_ids=request.filter_profile_ids,
                filter_simulation_ids=request.filter_simulation_ids,
                filter_department_ids=request.filter_department_ids,
                profile_search=request.profile_search,
                simulation_search=request.simulation_search,
                department_search=request.department_search,
                flag_search=request.flag_search,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="cohort",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="delete",
            arguments=request.model_dump(mode="json"),
            response_model=DeleteCohortApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.idempotency_key,  # idempotency replay gate
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="delete_cohort",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
