"""Dashboard GET endpoint — thin HTTP adapter over the canonical shared operation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.dashboard.types import DashboardBundleResponse, DashboardRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter(prefix="/dashboard")


@router.post("", response_model=DashboardBundleResponse)
async def get_dashboard(
    dashboard_request: DashboardRequest,
    http_request: Request,
    response: Response,
):
    try:
        # Lazy imports to avoid circular import
        from app.infra.attempt.group import group_attempt_impl
        from app.infra.dashboard.get import get_dashboard_impl_cached

        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401, detail="Profile ID is required. Please sign in again."
            )

        pool = get_pool()
        redis = get_redis_client()
        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_attempt_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> DashboardBundleResponse:
            response_data, cache_hit = await get_dashboard_impl_cached(
                pool,
                dashboard_request,
                profile_id=profile_id,
                bypass_cache=bypass_cache,
                cache_key_path=http_request.url.path,
            )
            response.headers["X-Cache-Hit"] = "1" if cache_hit else "0"
            return response_data

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="dashboard",
            arguments=dashboard_request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=DashboardBundleResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
        response.headers["X-Cache-Tags"] = "artifacts,dashboard,views,analytics"
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
            operation="artifacts_dashboard",
            request=http_request,
        )
