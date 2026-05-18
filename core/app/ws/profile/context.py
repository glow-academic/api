"""Input: profile.context"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.profile.context import context_profile_impl

internal_sio = get_internal_sio()


@sio.on("profile.context")  # type: ignore
async def profile_context(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    pool = get_pool()
    redis = get_redis_client()
    bypass_cache = data.get("bypass_cache", False)

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="profile",
        operation="context",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: context_profile_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            bypass_cache=bypass_cache,
            is_emulation=identity.is_emulation,
            emulation_depth=identity.emulation_depth,
        ),
        arguments={"profile_id": str(identity.profile_id)},
    )
