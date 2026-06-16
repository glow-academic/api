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

    # Guard the UUID parse on raw client input BEFORE it reaches the runner —
    # an unguarded ``UUID(...)`` there raises inside the audit wrapper, which
    # re-raises out of this fire-and-forget socket handler as an unretrieved-task
    # traceback and leaks the raw error into the payload. Every sibling handler
    # (attempt/chat/audio.py, voice.py, output.py) guards this same way.
    try:
        target_uuid = UUID(str(target_profile_id))
    except (ValueError, TypeError):
        await internal_sio.emit("profile.emulate.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": "target_profile_id must be a valid UUID.",
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
        runner=lambda: emulate_profile_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            target_profile_id=target_uuid,
            ttl_minutes=ttl_minutes,
            bypass_cache=bypass_cache,
            actor_profile_id=identity.actor_profile_id,
        ),
        arguments={
            "target_profile_id": str(target_profile_id),
            "ttl_minutes": ttl_minutes,
        },
    )
