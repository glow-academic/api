"""Group artifact endpoint — thin HTTP adapter over the canonical shared operation."""

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.group.get import get_group_impl
from app.infra.group.types import (
    GetGroupDetailRequest,
    GetGroupDetailResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/get", response_model=GetGroupDetailResponse)
async def get_group(
    request: GetGroupDetailRequest,
    http_request: Request,
    response: Response,
) -> GetGroupDetailResponse:
    """Get detailed group information with all runs and messages."""
    tags = ["artifacts", "group", "detail"]
    bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

    body_dict = request.model_dump(mode="json")
    cache_key_val = cache_key(http_request.url.path, body_dict)

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            response.headers["X-Cache-Tags"] = ",".join(tags)
            response.headers["X-Cache-Hit"] = "1"
            return GetGroupDetailResponse.model_validate(cached["data"])

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> GetGroupDetailResponse:
            return await get_group_impl(
                pool,
                profile_id=profile_id,
                group_id=request.group_id,
                redis=redis,
                bypass_cache=bypass_cache,
                message_limit=request.message_limit,
                message_offset=request.message_offset,
            )

        api_response = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="group",
            profile_id=profile_id,
            session_id=http_request.state.session_id,
            group_id=request.group_id,
            operation="get",
            arguments=body_dict,
            bypass_cache=bypass_cache,
            response_model=GetGroupDetailResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        await set_cached(
            cache_key_val,
            {"data": api_response.model_dump(mode="json")},
            ttl=300,
            tags=tags,
            redis=get_redis_client(),
        )
        response.headers["X-Cache-Tags"] = ",".join(tags)
        response.headers["X-Cache-Hit"] = "0"
        return api_response
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="get_group",
            request=http_request,
        )
