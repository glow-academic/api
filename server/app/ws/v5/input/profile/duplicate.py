"""Input: profile.duplicate"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.profile.duplicate import duplicate_profile_impl
from app.infra.profile.types import DuplicateProfileApiRequest

internal_sio = get_internal_sio()


@sio.on("profile.duplicate")  # type: ignore
async def profile_duplicate(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DuplicateProfileApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("profile.duplicate.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="profile",
        operation="duplicate",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: duplicate_profile_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            target_profile_id=payload.target_profile_id,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
