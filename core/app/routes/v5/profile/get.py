"""Profile GET endpoint — thin HTTP adapter over the canonical shared operation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.profile.get import get_profile_impl
from app.infra.profile.types import (
    GetProfileApiRequest,
    GetProfileApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/get", response_model=GetProfileApiResponse)
async def get_profile(
    request: GetProfileApiRequest,
    http_request: Request,
    response: Response,
) -> GetProfileApiResponse:
    """Get profile information using the canonical shared profile operation."""
    bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

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

        async def _runner() -> GetProfileApiResponse:
            return await get_profile_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                target_profile_id=request.target_profile_id,
                draft_id=request.draft_id,
                bypass_cache=bypass_cache,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="profile",
            profile_id=profile_id,
            session_id=session_id,
            draft_id=request.draft_id,
            operation="get",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=GetProfileApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Cache-Tags"] = "profiles"
        response.headers["X-Cache-Hit"] = "0"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="get_profile",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
