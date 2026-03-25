"""Profile unemulate endpoint — thin route, delegates to infra.

Consumes the innermost emulation grant to peel one layer.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.identity.emulate import resolve_unemulation
from app.infra.profile.types import UnemulateProfileApiResponse
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/unemulate", response_model=UnemulateProfileApiResponse)
async def unemulate_profile(
    http_request: Request,
    response: Response,
) -> UnemulateProfileApiResponse:
    """Exit innermost emulation layer. Next request resolves one layer less."""
    try:
        profile_id = getattr(http_request.state, "profile_id", None)
        if not profile_id:
            raise HTTPException(status_code=401, detail="Missing profile")

        identity = getattr(http_request.state, "identity", None)
        actor_profile_id = (
            getattr(identity, "actor_profile_id", None) if identity else None
        )
        session_id = getattr(http_request.state, "session_id", None)

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> UnemulateProfileApiResponse:
            origin = actor_profile_id or UUID(profile_id)
            result = await resolve_unemulation(pool, actor_profile_id=origin)

            if not result.ok:
                raise HTTPException(
                    status_code=400, detail=result.reason or "Cannot exit emulation"
                )

            tags = ["profile"]
            await invalidate_tags(tags, redis=redis)
            response.headers["X-Invalidate-Tags"] = ",".join(tags)

            return UnemulateProfileApiResponse(ok=result.ok, reason=result.reason)

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="profile",
            profile_id=UUID(profile_id),
            session_id=session_id,
            operation="unemulate",
            arguments={"profile_id": str(profile_id)},
            response_model=UnemulateProfileApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="unemulate_profile",
            request=http_request,
        )
