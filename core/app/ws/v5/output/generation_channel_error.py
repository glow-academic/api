"""Output: generation_channel (type=error)"""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event

internal_sio = get_internal_sio()


@internal_sio.on("generation_channel")  # type: ignore
async def generation_error_output(data: dict[str, Any]) -> None:
    if data.get("type") != "error":
        return
    sid = data.get("sid", "")
    artifact_type = data.get("artifact_type", "unknown")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    event_name = f"{artifact_type}_generation_error"
    if call_id:
        append_call_event(UUID(call_id), event_name, data, UPLOAD_FOLDER)
    for room in rooms:
        await sio.emit(event_name, data, room=room)
