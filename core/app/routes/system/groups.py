"""POST /system/groups — thin HTTP adapter over groups_system_impl.

Adds the HTTP-edge caching layer; all business logic lives in
``app.infra.system.groups``. Routed through the audit wrapper so ``snapshot_key``
replays a consistent view across related reads.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.pricing.types import ListPricingRequest, ListPricingResponse
from app.infra.system.group import group_system_impl
from app.infra.system.groups import ProfileNotFoundError, groups_system_impl
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/groups", response_model=ListPricingResponse)
async def search_groups(
    request: ListPricingRequest,
    http_request: Request,
    response: Response,
) -> ListPricingResponse:
    """Get paginated groups list with cost data (canonical groups list)."""
    tags = ["artifacts", "groups", "list"]
    bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"
    cache_key_val = cache_key(http_request.url.path, request.model_dump(mode="json"))

    try:
        pool = get_pool()
        if not pool:
            raise RuntimeError("Database pool not initialized")

        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )
        session_id = http_request.state.session_id
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID is required.")

        redis = get_redis_client()

        group_id = None
        group_result = await group_system_impl(
            pool, redis, profile_id=profile_id, session_id=session_id, id_only=True,
        )
        group_id = group_result.group_id

        async def _runner() -> ListPricingResponse:
            if not bypass_cache:
                cached = await get_cached(cache_key_val, redis=redis)
                if cached:
                    response.headers["X-Cache-Hit"] = "1"
                    return ListPricingResponse.model_validate(cached["data"])
            try:
                api_response = await groups_system_impl(
                    pool,
                    redis,
                    profile_id=profile_id,
                    session_id=session_id,
                    request=request,
                    bypass_cache=bypass_cache,
                )
            except ProfileNotFoundError as e:
                raise HTTPException(status_code=401, detail=str(e))
            await set_cached(
                cache_key_val,
                {"data": api_response.model_dump(mode="json")},
                ttl=300,
                tags=tags,
                redis=redis,
            )
            response.headers.setdefault("X-Cache-Hit", "0")
            return api_response

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="system",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="groups",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=ListPricingResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.snapshot_key,  # read snapshot: replay this view if echoed
        )
        response.headers["X-Cache-Tags"] = ",".join(tags)
        return result

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="groups_search",
            request=http_request,
        )
