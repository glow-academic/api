"""Input: attempt.leave — unsubscribe from events for a group."""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity


@sio.on("attempt.leave")  # type: ignore
async def attempt_leave(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    group_id = str(data.get("group_id", ""))
    if not group_id:
        return

    async def _runner() -> dict[str, Any]:
        await sio.leave_room(sid, group_id)
        return {"group_id": group_id, "success": True}

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="leave",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=_runner,
        arguments={"group_id": group_id},
    )
