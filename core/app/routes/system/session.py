"""Session GET endpoint — thin HTTP adapter over the canonical shared operation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.session.get import get_session_detail_impl_cached
from app.infra.session.types import (
    GetSessionDetailRequest,
    GetSessionDetailResponse,
)
from app.infra.system.group import group_system_impl
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter(prefix="/session")


@router.post("", response_model=GetSessionDetailResponse)
async def get_session(
    request: GetSessionDetailRequest,
    http_request: Request,
    response: Response,
) -> GetSessionDetailResponse:
    """Get session detail with groups and timeline."""
    try:
        profile_id = http_request.state.profile_id
        actor_session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()
        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

        # Resolve time-windowed group for audit linking
        group_id = None
        session_id = actor_session_id or request.session_id
        if session_id:
            group_result = await group_system_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> GetSessionDetailResponse:
            response_data, cache_hit = await get_session_detail_impl_cached(
                pool,
                profile_id=profile_id,
                session_id=request.session_id,
                bypass_cache=bypass_cache,
                cache_key_path=http_request.url.path,
            )
            response.headers["X-Cache-Hit"] = "1" if cache_hit else "0"
            return response_data

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="system",
            profile_id=profile_id,
            session_id=actor_session_id,
            group_id=group_id,
            operation="session",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=GetSessionDetailResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
        response.headers["X-Cache-Tags"] = "artifacts,session"
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
            operation="artifacts_session",
            request=http_request,
        )
