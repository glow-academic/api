"""Output: attempt.chat_grade.failed"""

from typing import Any

from app.infra.globals import get_internal_sio, sio

internal_sio = get_internal_sio()


@internal_sio.on("attempt.chat_grade.failed")  # type: ignore
async def chat_grade_failed(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    for room in rooms:
        await sio.emit("attempt.chat_grade.failed", data, room=room)
