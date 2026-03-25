"""Cohort update endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.cohort_update.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.cohort.update import update_cohort_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.cohort.types import (
    UpdateCohortApiRequest,
    UpdateCohortApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/update", response_model=UpdateCohortApiResponse)
async def update_cohort(
    request: UpdateCohortApiRequest,
    http_request: Request,
    response: Response,
) -> UpdateCohortApiResponse:
    """Update cohorts using composable infra architecture."""
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

        async def _runner() -> UpdateCohortApiResponse:
            return await update_cohort_impl(
                pool,
                redis,
                profile_id=profile_id,
                items=request.cohorts,
                session_id=session_id,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="cohort",
            profile_id=profile_id,
            session_id=session_id,
            operation="update",
            arguments={
                "cohorts": [item.model_dump(mode="json") for item in request.cohorts]
            },
            response_model=UpdateCohortApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "cohorts"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="update_cohort",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
