"""Provider duplicate endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.provider.duplicate.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.provider.duplicate import duplicate_provider_impl
from app.infra.provider.types import (
    DuplicateProviderApiRequest,
    DuplicateProviderApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post(
    "/duplicate",
    response_model=DuplicateProviderApiResponse,
)
async def duplicate_provider(
    request: DuplicateProviderApiRequest,
    http_request: Request,
    response: Response,
) -> DuplicateProviderApiResponse:
    """Duplicate a provider — composable infra architecture."""
    tags = ["providers"]

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

        async def _runner() -> DuplicateProviderApiResponse:
            return await duplicate_provider_impl(
                pool,
                redis,
                profile_id=profile_id,
                provider_id=request.provider_id,
                session_id=session_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="provider",
            profile_id=profile_id,
            session_id=session_id,
            operation="duplicate",
            arguments=request.model_dump(mode="json"),
            response_model=DuplicateProviderApiResponse,
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
            operation="duplicate_provider",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
