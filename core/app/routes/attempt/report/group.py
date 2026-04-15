"""Reports group endpoint — thin HTTP adapter.

Core logic lives in app.infra.reports.group.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.reports.group import (
    GroupReportsApiRequest,
    GroupReportsApiResponse,
    group_reports_impl,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/group", response_model=GroupReportsApiResponse)
async def group_reports(
    request: GroupReportsApiRequest,
    http_request: Request,
    response: Response,
) -> GroupReportsApiResponse:
    """Resolve or create a reports group with optional naming."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )
        if not session_id:
            raise HTTPException(
                status_code=401,
                detail="Session ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> GroupReportsApiResponse:
            return await group_reports_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                request=request,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="reports",
            profile_id=profile_id,
            session_id=session_id,
            operation="group",
            group_id=request.group_id,
            arguments=request.model_dump(mode="json"),
            response_model=GroupReportsApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "groups"
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="group_reports",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
