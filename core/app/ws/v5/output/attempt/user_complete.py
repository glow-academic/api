"""Output: attempt.user_complete"""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event

internal_sio = get_internal_sio()


@internal_sio.on("attempt_user_complete")  # type: ignore
async def attempt_user_complete_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "attempt.user_complete", data, UPLOAD_FOLDER)
    for room in rooms:
        await sio.emit("attempt.user_complete", data, room=room)
