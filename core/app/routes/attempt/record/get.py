"""Record artifact — get endpoint (profile report).

Thin HTTP adapter over the canonical shared operation in
``app.infra.record.get``.
"""

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.attempt.group import group_attempt_impl
from app.infra.dashboard.types import DashboardBundleResponse
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.record.get import get_record_impl_cached
from app.infra.record.types import RecordRequest
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/get", response_model=DashboardBundleResponse)
async def get_record(
    request: RecordRequest,
    http_request: Request,
    response: Response,
) -> DashboardBundleResponse:
    """Get record profile report — dashboard metrics for a single profile."""
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

        redis = get_redis_client()
        session_id = http_request.state.session_id
        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_attempt_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> DashboardBundleResponse:
            bundle, cache_hit = await get_record_impl_cached(
                pool,
                request,
                profile_id=profile_id,
                bypass_cache=bypass_cache,
                cache_key_path=http_request.url.path,
            )
            response.headers["X-Cache-Hit"] = "1" if cache_hit else "0"
            return bundle

        api_response = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="record",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="get",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=DashboardBundleResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
        response.headers["X-Cache-Tags"] = "artifacts,record,views,analytics"
        response.headers.setdefault("X-Cache-Hit", "0")
        return api_response

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="artifacts_record_get",
            request=http_request,
        )
