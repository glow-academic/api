"""Output: attempt.chat_message.started"""

from typing import Any

from app.infra.globals import get_internal_sio, sio

internal_sio = get_internal_sio()


@internal_sio.on("attempt.chat_message.started")  # type: ignore
async def attempt_chat_message_started(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    for room in rooms:
        await sio.emit("attempt.chat_message.started", data, room=room)
