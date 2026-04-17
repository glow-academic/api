"""Output: attempt.generate.call.start"""

from typing import Any

from app.infra.globals import get_internal_sio, sio

internal_sio = get_internal_sio()


@internal_sio.on("attempt.generate.call.start")  # type: ignore
async def attempt_generate_call_start(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    for room in rooms:
        await sio.emit("attempt.generate.call.start", data, room=room)
