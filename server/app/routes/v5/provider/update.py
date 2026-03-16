"""Provider update endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.provider.update.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.provider.update import update_provider_impl
from app.infra.provider.types import (
    UpdateProviderApiRequest,
    UpdateProviderApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/update", response_model=UpdateProviderApiResponse)
async def update_provider(
    request: UpdateProviderApiRequest,
    http_request: Request,
    response: Response,
) -> UpdateProviderApiResponse:
    """Update providers using composable infra architecture."""
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

        async def _runner() -> UpdateProviderApiResponse:
            return await update_provider_impl(
                pool,
                redis,
                profile_id=profile_id,
                items=request.providers,
                session_id=session_id,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="provider",
            profile_id=profile_id,
            session_id=session_id,
            operation="update",
            arguments={
                "providers": [
                    item.model_dump(mode="json") for item in request.providers
                ]
            },
            response_model=UpdateProviderApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "providers"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="update_provider",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
