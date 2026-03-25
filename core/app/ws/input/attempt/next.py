"""Input: attempt.next"""

from typing import Any

from app.infra.globals import get_internal_sio, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.attempt.next import attempt_next_internal_impl

internal_sio = get_internal_sio()


@sio.on("attempt.next")  # type: ignore
async def attempt_next(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        await attempt_next_internal_impl({
            **data,
            "sid": sid,
            "profile_id": str(identity.profile_id),
            "session_id": str(identity.session_id),
        })
    except Exception as e:
        await internal_sio.emit("attempt.next.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": type(e).__name__,
        })
