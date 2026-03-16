"""Auth delete endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.auth.delete.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.auth.delete import delete_auth_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.auth.types import (
    DeleteAuthApiRequest,
    DeleteAuthApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/delete", response_model=DeleteAuthApiResponse)
async def delete_auth(
    request: DeleteAuthApiRequest,
    http_request: Request,
    response: Response,
) -> DeleteAuthApiResponse:
    """Bulk delete auths — composable infra architecture."""
    tags = ["auths"]

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

        async def _runner() -> DeleteAuthApiResponse:
            return await delete_auth_impl(
                pool,
                redis,
                profile_id=profile_id,
                auth_ids=request.auth_ids,
                session_id=session_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="auth",
            profile_id=profile_id,
            session_id=session_id,
            operation="delete",
            arguments=request.model_dump(mode="json"),
            response_model=DeleteAuthApiResponse,
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
            operation="delete_auth",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
