"""POST /context — identity + permissions + theme.

Thin route — delegates to context_profile_impl.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.profile.context import context_profile_impl
from app.infra.profile.group import group_profile_impl
from app.infra.profile.types import ProfileContextApiResponse
from app.infra.shared_types import GetProfileContextApiRequest
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/context", response_model=ProfileContextApiResponse, tags=["profiles"])
async def get_profile_context(
    request: GetProfileContextApiRequest,
    http_request: Request,
    response: Response,
) -> ProfileContextApiResponse:
    """Identity + permissions + theme context endpoint."""
    try:
        try:
            profile_id = http_request.state.profile_id
        except AttributeError:
            profile_id = None

        if not profile_id:
            raise HTTPException(status_code=404, detail="Profile ID is required")

        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"
        pool = get_pool()
        redis = get_redis_client()
        session_id = getattr(http_request.state, "session_id", None)

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_profile_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        req_identity = getattr(http_request.state, "identity", None)
        is_emulation = (
            getattr(req_identity, "is_emulation", False) if req_identity else False
        )
        emulation_depth = (
            getattr(req_identity, "emulation_depth", 0) if req_identity else 0
        )

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="profile",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="context",
            arguments={"profile_id": str(profile_id)},
            bypass_cache=bypass_cache,
            response_model=ProfileContextApiResponse,
            runner=lambda: context_profile_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                bypass_cache=bypass_cache,
                is_emulation=is_emulation,
                emulation_depth=emulation_depth,
            ),
            upload_folder=get_upload_folder(),
        )

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="get_profile_context",
            request=http_request,
        )
