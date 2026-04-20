"""Output: attempt.generate.audio.response_cancelled

Emitted on barge-in — the user began speaking while the assistant was mid
response, so the provider cancelled the in-flight response. Persists the
event, forwards to the client, and runs ``audio_response_cancelled_impl``.
"""

from typing import Any
from uuid import UUID

from app.infra.attempt.workflows import audio_response_cancelled_impl
from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, sio
from app.infra.tools.entries.append_call_event import append_call_event
from app.infra.websocket.socket_event import make_emit

internal_sio = get_internal_sio()


@internal_sio.on("attempt.generate.audio.response_cancelled")  # type: ignore
async def attempt_generate_audio_response_cancelled(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    call_id = data.get("call_id")
    if call_id:
        append_call_event(
            UUID(call_id),
            "attempt.generate.audio.response_cancelled",
            data,
            UPLOAD_FOLDER,
        )
    for room in rooms:
        await sio.emit(
            "attempt.generate.audio.response_cancelled", data, room=room,
        )

    await audio_response_cancelled_impl(data, emit=make_emit())
