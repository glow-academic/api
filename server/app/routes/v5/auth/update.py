"""Auth update endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.auth.update.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.auth.update import update_auth_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.auth.types import (
    UpdateAuthApiRequest,
    UpdateAuthApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/update", response_model=UpdateAuthApiResponse)
async def update_auth(
    request: UpdateAuthApiRequest,
    http_request: Request,
    response: Response,
) -> UpdateAuthApiResponse:
    """Update auths using composable infra architecture."""
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

        async def _runner() -> UpdateAuthApiResponse:
            return await update_auth_impl(
                pool,
                redis,
                profile_id=profile_id,
                items=request.auths,
                session_id=session_id,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="auth",
            profile_id=profile_id,
            session_id=session_id,
            operation="update",
            arguments={
                "auths": [item.model_dump(mode="json") for item in request.auths]
            },
            response_model=UpdateAuthApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "auths"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="update_auth",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
