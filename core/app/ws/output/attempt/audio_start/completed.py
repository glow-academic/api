"""Output: attempt.chat.voice_ready (forward → connected clients).

audio_session_start_impl emits the renamed ``attempt.chat.voice_ready``
internal-bus event; this handler relays the same name to the SIO rooms
so the client's ``use-attempt-voice.ts`` listener sees it and arms the
mic UI. The legacy ``attempt.audio_start.completed`` name was retired
with the chat→voice migration.
"""

from typing import Any

from app.infra.globals import get_internal_sio, sio

internal_sio = get_internal_sio()


@internal_sio.on("attempt.chat.voice_ready")  # type: ignore
async def chat_voice_ready(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    for room in rooms:
        await sio.emit("attempt.chat.voice_ready", data, room=room)
