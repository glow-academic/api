"""Profile emulate endpoint — thin route, delegates to infra.

Creates an emulation grant. resolve_identity() picks it up on next request.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.identity.emulate import resolve_emulation
from app.infra.profile.types import (
    EmulateProfileApiRequest,
    EmulateProfileApiResponse,
)
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/emulate", response_model=EmulateProfileApiResponse)
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

        async def _runner() -> EmulateProfileApiResponse:
            result = await resolve_emulation(
                pool,
                redis,
                requester_profile_id=UUID(profile_id),
                target_profile_id=request.target_profile_id,
                ttl_minutes=request.ttl_minutes or 120,
                bypass_cache=bypass_cache,
                actor_profile_id=actor_profile_id,
            )

            if not result.allowed:
                raise HTTPException(
                    status_code=403, detail=result.reason or "Forbidden"
                )

            tags = ["profile"]
            await invalidate_tags(tags, redis=redis)
            response.headers["X-Invalidate-Tags"] = ",".join(tags)

            return EmulateProfileApiResponse(
                allowed=result.allowed,
                reason=result.reason,
                grant_id=result.grant_id,
                expires_at=result.expires_at,
            )

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="profile",
            profile_id=UUID(profile_id),
            session_id=session_id,
            operation="emulate",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=EmulateProfileApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="emulate_profile",
            request=http_request,
        )
