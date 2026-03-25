"""Input: attempt.start"""

from typing import Any

from app.infra.globals import get_internal_sio, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.attempt.start import attempt_start_internal_impl

internal_sio = get_internal_sio()


@sio.on("attempt.start")  # type: ignore
async def attempt_start(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        await attempt_start_internal_impl({
            **data,
            "sid": sid,
            "profile_id": str(identity.profile_id),
            "session_id": str(identity.session_id),
        })
    except Exception as e:
        await internal_sio.emit("attempt.start.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": type(e).__name__,
        })
