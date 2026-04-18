"""Group name endpoint — thin HTTP adapter.

Core logic lives in app.infra.group.name.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.system.group import group_system_impl
from app.infra.group.name import (
    NameGroupApiRequest,
    NameGroupApiResponse,
    name_group_impl,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post(
    "/name",
    response_model=NameGroupApiResponse,
)
async def name_group(
    request: NameGroupApiRequest,
    http_request: Request,
    response: Response,
) -> NameGroupApiResponse:
    """Set or update a group's name."""
    tags = ["groups"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        session_id = http_request.state.session_id
        if not session_id:
            raise HTTPException(status_code=401, detail="Session ID is required.")

        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_system_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> NameGroupApiResponse:
            return await name_group_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                request=request,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="group",
            operation="name",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            arguments=request.model_dump(mode="json"),
            response_model=NameGroupApiResponse,
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
            operation="name_group",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
