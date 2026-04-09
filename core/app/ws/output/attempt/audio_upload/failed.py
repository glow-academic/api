"""Output: attempt.audio_upload.failed"""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event

internal_sio = get_internal_sio()


@internal_sio.on("attempt.audio_upload.failed")  # type: ignore
async def attempt_audio_upload_failed(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "attempt.audio_upload.failed", data, UPLOAD_FOLDER)
    for room in rooms:
        await sio.emit("attempt.audio_upload.failed", data, room=room)
