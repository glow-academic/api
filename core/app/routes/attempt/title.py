"""Attempt title endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.attempt.title (which
wraps the shared title_group_impl). Writes a new ``group_names_entry`` row
renaming the attempt's associated group.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.attempt.group import group_attempt_impl
from app.infra.attempt.title import (
    TitleAttemptApiRequest,
    TitleAttemptApiResponse,
    title_attempt_impl,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/title", response_model=TitleAttemptApiResponse)
async def title_attempt(
    request: TitleAttemptApiRequest,
    http_request: Request,
    response: Response,
) -> TitleAttemptApiResponse:
    """Rename a attempt's group (writes group_names_entry)."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id or not session_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID and session ID are required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking (session context).
        group_result = await group_attempt_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
        )
        audit_group_id = group_result.group_id

        async def _runner() -> TitleAttemptApiResponse:
            return await title_attempt_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                request=request,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=session_id,
            group_id=audit_group_id,
            operation="title",
            arguments=request.model_dump(mode="json", exclude_none=True),
            response_model=TitleAttemptApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "groups"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="title_attempt",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
