"""System group router — single canonical POST /system/group endpoint.

Merged: previously had bare POST (lean resolve) + /get (full detail tree).
Now one endpoint: pass ``include_detail=True`` in the body to get the detail
tree alongside the lean resolve. Internal audit-linking callers leave
``include_detail`` at the default ``False`` for the cheap path.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.system.group import (
    GroupSystemApiRequest,
    GroupSystemApiResponse,
    group_system_impl,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter(prefix="/group", tags=["group"])


@router.post("", response_model=GroupSystemApiResponse)
async def group_system(
    request: GroupSystemApiRequest,
    http_request: Request,
    response: Response,
) -> GroupSystemApiResponse:
    """Resolve or create the session's system group, optionally naming it."""
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

        async def _runner(group_id: UUID) -> GroupSystemApiResponse:
            scoped_request = request.model_copy(update={'group_id': group_id})
            return await group_system_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                request=scoped_request,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="system",
            profile_id=profile_id,
            session_id=session_id,
            group_id=request.group_id,

            mint_group_id_if_missing=True,
            operation="group",
            arguments=request.model_dump(mode="json"),
            response_model=GroupSystemApiResponse,
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
            operation="group_system",
            request=http_request,
        )
