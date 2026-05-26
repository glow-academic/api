"""Profile unemulate endpoint — thin route, delegates to infra.

Consumes the innermost emulation grant to peel one layer.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.profile.group import group_profile_impl
from app.infra.profile.types import (
    UnemulateProfileApiRequest,
    UnemulateProfileApiResponse,
)
from app.infra.profile.unemulate import unemulate_profile_impl
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/unemulate", response_model=UnemulateProfileApiResponse, tags=["profile"])
async def unemulate_profile(
    request: UnemulateProfileApiRequest,
    http_request: Request,
    response: Response,
) -> UnemulateProfileApiResponse:
    """Exit emulation for a specific target profile."""
    try:
        profile_id = getattr(http_request.state, "profile_id", None)
        if not profile_id:
            raise HTTPException(status_code=401, detail="Missing profile")

        identity = getattr(http_request.state, "identity", None)
        actor_profile_id = (
            getattr(identity, "actor_profile_id", None) if identity else None
        )
        session_id = getattr(http_request.state, "session_id", None)

        target_profile_id = (
            UUID(request.target_profile_id) if request.target_profile_id else None
        )

        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_profile_impl(
                pool, redis, profile_id=UUID(profile_id), session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        is_ack = request.accept is not None and request.idempotency_key is not None

        # ``call_id`` is threaded in by the audit wrapper (signature opt-in).
        async def _runner(call_id: UUID | None = None) -> UnemulateProfileApiResponse:
            return await unemulate_profile_impl(
                pool,
                redis,
                profile_id=UUID(profile_id),
                actor_profile_id=actor_profile_id,
                target_profile_id=target_profile_id,
                soft=request.soft,
                accept=request.accept,
                idempotency_key=request.idempotency_key,
                call_id=call_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="profile",
            profile_id=UUID(profile_id),
            session_id=session_id,
            group_id=group_id,
            operation="unemulate",
            # On ack, carry only `accept` so the gate's _is_bare_ack skips it.
            arguments={"accept": request.accept} if is_ack else {
                "profile_id": str(profile_id),
                "target_profile_id": str(target_profile_id),
            },
            response_model=UnemulateProfileApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.idempotency_key,  # idempotency replay gate
        )

        response.headers["X-Invalidate-Tags"] = "profile"
        return result

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="unemulate_profile",
            request=http_request,
        )
