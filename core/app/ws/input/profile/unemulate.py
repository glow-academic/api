"""Input: profile.unemulate"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.profile.unemulate import unemulate_profile_impl

internal_sio = get_internal_sio()


@sio.on("profile.unemulate")  # type: ignore
async def profile_unemulate(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="profile",
        operation="unemulate",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: unemulate_profile_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            actor_profile_id=identity.actor_profile_id,
        ),
        arguments={"profile_id": str(identity.profile_id)},
    )
