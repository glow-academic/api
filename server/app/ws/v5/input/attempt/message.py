"""Input: attempt.message"""

from typing import Any

from app.infra.globals import get_internal_sio, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.websocket.session_store import get_session_by_chat_id
from app.infra.attempt.message import attempt_message_internal_impl

internal_sio = get_internal_sio()


@sio.on("attempt.message")  # type: ignore
async def attempt_message(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    # If there's an active audio session, inject text into its queue
    chat_id = data.get("chat_id")
    message = data.get("message")
    if chat_id and message:
        session = get_session_by_chat_id(str(chat_id))
        if session:
            await session.inbound_queue.put({"type": "text", "message": message})
            return

    try:
        await attempt_message_internal_impl({
            **data,
            "sid": sid,
            "profile_id": str(identity.profile_id),
            "session_id": str(identity.session_id),
        })
    except Exception as e:
        await internal_sio.emit("attempt.message.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": type(e).__name__,
        })
