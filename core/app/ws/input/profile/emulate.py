"""Input: profile.emulate"""

from typing import Any
from uuid import UUID

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.profile.emulate import emulate_profile_impl

internal_sio = get_internal_sio()


@sio.on("profile.emulate")  # type: ignore
async def profile_emulate(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    target_profile_id = data.get("target_profile_id")
    if not target_profile_id:
        await internal_sio.emit("profile.emulate.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": "target_profile_id is required.",
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()
    bypass_cache = data.get("bypass_cache", False)
    ttl_minutes = data.get("ttl_minutes") or 120

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="profile",
        operation="emulate",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: emulate_profile_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            target_profile_id=UUID(target_profile_id),
            ttl_minutes=ttl_minutes,
            bypass_cache=bypass_cache,
            actor_profile_id=identity.actor_profile_id,
        ),
        arguments={
            "target_profile_id": str(target_profile_id),
            "ttl_minutes": ttl_minutes,
        },
    )
