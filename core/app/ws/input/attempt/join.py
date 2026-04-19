"""Input: attempt.join — subscribe to events for a group."""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("attempt.join")  # type: ignore
async def attempt_join(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    group_id = str(data.get("group_id", ""))
    if not group_id:
        return

    async def _runner() -> dict[str, Any]:
        await sio.enter_room(sid, group_id)

        await internal_sio.emit(
            "attempt_joined",
            {
                "sid": sid,
                "rooms": [sid],
                "group_id": group_id,
                "success": True,
            },
        )

        return {"group_id": group_id, "success": True}

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="join",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=_runner,
        arguments={"group_id": group_id},
    )
