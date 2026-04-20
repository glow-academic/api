"""Output: attempt.generate.audio.session_complete

Emitted when the realtime voice session closes. Runs ``audio_stop_impl``
which records the conversation completion in the DB and drives the
``attempt.chat.voice_ended`` / silence-completed client notifications.
"""

from typing import Any
from uuid import UUID

from app.infra.attempt.workflows import audio_stop_impl
from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.websocket.socket_event import make_emit

internal_sio = get_internal_sio()


@internal_sio.on("attempt.generate.audio.session_complete")  # type: ignore
async def attempt_generate_audio_session_complete(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    if call_id:
        append_call_event(
            UUID(call_id),
            "attempt.generate.audio.session_complete",
            data,
            UPLOAD_FOLDER,
        )
    for room in rooms:
        await sio.emit(
            "attempt.generate.audio.session_complete", data, room=room,
        )

    await audio_stop_impl(data, emit=make_emit())
