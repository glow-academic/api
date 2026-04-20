"""Output: attempt.generate.audio.error

Persists the event, forwards to the client, and runs the domain translator
``audio_error_impl`` so attempt-namespace listeners see the canonical error.
"""

from typing import Any
from uuid import UUID

from app.infra.attempt.workflows import audio_error_impl
from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.websocket.socket_event import make_emit

internal_sio = get_internal_sio()


@internal_sio.on("attempt.generate.audio.error")  # type: ignore
async def attempt_generate_audio_error(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    if call_id:
        append_call_event(
            UUID(call_id), "attempt.generate.audio.error", data, UPLOAD_FOLDER,
        )
    for room in rooms:
        await sio.emit("attempt.generate.audio.error", data, room=room)

    await audio_error_impl(data, emit=make_emit())
