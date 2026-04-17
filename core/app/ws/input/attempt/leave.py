"""Input: attempt.leave"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity


@sio.on("attempt.leave")  # type: ignore
async def attempt_leave(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    chat_id = str(data.get("chat_id", ""))
    if not chat_id:
        return

    async def _runner() -> dict[str, Any]:
        room_name = f"attempt_{chat_id}"
        await sio.leave_room(sid, room_name)
        return {"chat_id": chat_id, "success": True}

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
        arguments={"chat_id": chat_id},
    )
