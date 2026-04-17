"""Output: attempt.generate.text.complete"""

from typing import Any

from app.infra.globals import get_internal_sio, sio

internal_sio = get_internal_sio()


@internal_sio.on("attempt.generate.text.complete")  # type: ignore
async def attempt_generate_text_complete(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    for room in rooms:
        await sio.emit("attempt.generate.text.complete", data, room=room)
