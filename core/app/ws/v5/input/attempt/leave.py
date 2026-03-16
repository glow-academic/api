"""Input: attempt.leave"""

from typing import Any

from app.infra.globals import sio


@sio.on("attempt.leave")  # type: ignore
async def attempt_leave(sid: str, data: dict[str, Any]) -> None:
    chat_id = str(data.get("chat_id", ""))
    if not chat_id:
        return

    room_name = f"attempt_{chat_id}"
    await sio.leave_room(sid, room_name)
