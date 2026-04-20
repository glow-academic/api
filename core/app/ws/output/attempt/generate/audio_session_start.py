"""Output: attempt.generate.audio.session_start

Emitted when the realtime voice session opens. Runs
``audio_session_start_impl`` which emits ``attempt_audio_ready`` →
``attempt.chat.voice_ready`` for the client.
"""

from typing import Any
from uuid import UUID

from app.infra.attempt.workflows import audio_session_start_impl
from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.websocket.socket_event import make_emit

internal_sio = get_internal_sio()


@internal_sio.on("attempt.generate.audio.session_start")  # type: ignore
async def attempt_generate_audio_session_start(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    if call_id:
        append_call_event(
            UUID(call_id),
            "attempt.generate.audio.session_start",
            data,
            UPLOAD_FOLDER,
        )
    for room in rooms:
        await sio.emit(
            "attempt.generate.audio.session_start", data, room=room,
        )

    await audio_session_start_impl(data, emit=make_emit())
