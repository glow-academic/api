"""Activity GET endpoint — thin HTTP adapter over the canonical shared operation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.activity.get import get_activity_impl_cached
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.activity.types import ActivityRequest, ActivityResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/get", response_model=ActivityResponse)
async def get_activity(
    request: ActivityRequest,
    http_request: Request,
    response: Response,
) -> ActivityResponse:
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401, detail="Profile ID is required. Please sign in again."
            )

        pool = get_pool()
        redis = get_redis_client()
        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

        async def _runner() -> ActivityResponse:
            response_data, cache_hit = await get_activity_impl_cached(
                pool,
                request,
                profile_id=profile_id,
                bypass_cache=bypass_cache,
                cache_key_path=http_request.url.path,
            )
            response.headers["X-Cache-Hit"] = "1" if cache_hit else "0"
            return response_data

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="activity",
            profile_id=profile_id,
            session_id=session_id,
            operation="get",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=ActivityResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
        response.headers["X-Cache-Tags"] = "artifacts,activity"
        response.headers.setdefault("X-Cache-Hit", "0")
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="artifacts_activity_get",
            request=http_request,
        )
