"""Model group endpoint — thin HTTP adapter.

Core logic lives in app.infra.model.group.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.model.group import (
    GroupModelApiRequest,
    GroupModelApiResponse,
    group_model_impl,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/group", response_model=GroupModelApiResponse)
async def group_model(
    request: GroupModelApiRequest,
    http_request: Request,
    response: Response,
) -> GroupModelApiResponse:
    """Resolve or create a model group with optional naming."""
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

        async def _runner(group_id: UUID) -> GroupModelApiResponse:
            scoped_request = request.model_copy(update={'group_id': group_id})
            return await group_model_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                request=scoped_request,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="model",
            profile_id=profile_id,
            session_id=session_id,
            operation="group",
            group_id=request.group_id,

            mint_group_id_if_missing=True,
            arguments=request.model_dump(mode="json"),
            response_model=GroupModelApiResponse,
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
            operation="group_model",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
