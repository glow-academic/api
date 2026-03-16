"""Attempt detail endpoint — thin HTTP adapter over the canonical shared operation."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.attempt.get import get_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.attempt.types import (
    GetAttemptDetailRequest,
    GetAttemptDetailResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/get", response_model=GetAttemptDetailResponse)
async def attempt_get(
    request: GetAttemptDetailRequest,
    http_request: Request,
    response: Response,
) -> GetAttemptDetailResponse:
    """Get attempt detail with the canonical shared attempt bundle."""
    tags = ["attempt"]
    bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

    try:
        profile_id_str = http_request.state.profile_id
        if not profile_id_str:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()
        profile_id = UUID(profile_id_str)
        cache_hit_holder = {"value": False}

        async def _runner() -> GetAttemptDetailResponse:
            response_data, cache_hit = await get_attempt_impl(
                pool,
                redis,
                profile_id=profile_id,
                attempt_id=request.attempt_id,
                bypass_cache=bypass_cache,
                cache_key_path=http_request.url.path,
            )
            cache_hit_holder["value"] = cache_hit
            return response_data

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=http_request.state.session_id,
            attempt_id=request.attempt_id,
            operation="get",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=GetAttemptDetailResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
        cache_hit = cache_hit_holder["value"]

        response.headers["X-Cache-Tags"] = ",".join(tags)
        response.headers["X-Cache-Hit"] = "1" if cache_hit else "0"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="attempt_get",
            request=http_request,
        )
