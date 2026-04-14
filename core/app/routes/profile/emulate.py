"""Profile emulate endpoint — thin route, delegates to infra.

Creates an emulation grant. resolve_identity() picks it up on next request.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.profile.emulate import emulate_profile_impl
from app.infra.profile.group import group_profile_impl
from app.infra.profile.types import (
    EmulateProfileApiRequest,
    EmulateProfileApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/emulate", response_model=EmulateProfileApiResponse, tags=["profiles"])
async def emulate_profile(
    request: EmulateProfileApiRequest,
    http_request: Request,
    response: Response,
) -> EmulateProfileApiResponse:
    """Create emulation grant. Next request will resolve to target profile."""
    try:
        profile_id = getattr(http_request.state, "profile_id", None)
        if not profile_id:
            raise HTTPException(status_code=401, detail="Missing requester profile")

        identity = getattr(http_request.state, "identity", None)
        actor_profile_id = (
            getattr(identity, "actor_profile_id", None) if identity else None
        )

        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"
        redis = get_redis_client()
        pool = get_pool()
        session_id = getattr(http_request.state, "session_id", None)

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_profile_impl(
                pool, redis, profile_id=UUID(profile_id), session_id=session_id,
            )
            group_id = group_result.group_id

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="profile",
            profile_id=UUID(profile_id),
            session_id=session_id,
            group_id=group_id,
            operation="emulate",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=EmulateProfileApiResponse,
            runner=lambda: emulate_profile_impl(
                pool,
                redis,
                profile_id=UUID(profile_id),
                target_profile_id=request.target_profile_id,
                ttl_minutes=request.ttl_minutes or 120,
                bypass_cache=bypass_cache,
                actor_profile_id=actor_profile_id,
            ),
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "profile"
        return result

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="emulate_profile",
            request=http_request,
        )
