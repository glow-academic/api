"""Output: attempt.chat_send.started"""

from typing import Any

from app.infra.globals import get_internal_sio, sio

internal_sio = get_internal_sio()


@internal_sio.on("attempt.chat_send.started")  # type: ignore
async def attempt_chat_send_started(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    for room in rooms:
        await sio.emit("attempt.chat_send.started", data, room=room)
