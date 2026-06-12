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


@router.post("/emulate", response_model=EmulateProfileApiResponse, tags=["profile"])
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

        # E2 — attribute the emulation grant + audit to the REAL actor A, not
        # the intermediate (effective) profile B. ``profile_id`` here is the
        # effective profile; while already emulating, ``actor_profile_id`` is
        # the real JWT actor. The audit record (artifact owner + session +
        # group) must show A emulated C, else the chained grant is durably
        # misattributed to B (repudiation). When emulating we resolve the
        # actor's own active session so the whole audit row is coherent.
        audit_profile_id = UUID(str(actor_profile_id)) if actor_profile_id else UUID(profile_id)
        audit_session_id = session_id
        if actor_profile_id and actor_profile_id != UUID(profile_id):
            # ``profile_id`` arg is a profile_artifact.id, so use the
            # artifact-id session resolver to get the actor's own session.
            from app.infra.identity.resolve_identity import get_or_create_session
            async with pool.acquire() as conn:
                audit_session_id = await get_or_create_session(conn, audit_profile_id)

        # Resolve time-windowed group for audit linking — against the
        # attributed (actor) profile/session so the audit owner is coherent.
        group_id = None
        if audit_session_id:
            group_result = await group_profile_impl(
                pool, redis, profile_id=audit_profile_id, session_id=audit_session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        is_ack = request.accept is not None and request.idempotency_key is not None

        # ``call_id`` is threaded in by the audit wrapper (signature opt-in) —
        # it's the server-minted calls_entry id the soft ledger keys on.
        async def _runner(call_id: UUID | None = None) -> EmulateProfileApiResponse:
            return await emulate_profile_impl(
                pool,
                redis,
                profile_id=UUID(profile_id),
                target_profile_id=request.target_profile_id,
                ttl_minutes=request.ttl_minutes or 120,
                bypass_cache=bypass_cache,
                actor_profile_id=actor_profile_id,
                soft=request.soft,
                accept=request.accept,
                idempotency_key=request.idempotency_key,
                call_id=call_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="profile",
            profile_id=audit_profile_id,
            session_id=audit_session_id,
            group_id=group_id,
            operation="emulate",
            # On ack, carry only `accept` so the gate's _is_bare_ack skips it.
            arguments={"accept": request.accept} if is_ack else request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=EmulateProfileApiResponse,
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
            operation="emulate_profile",
            request=http_request,
        )
