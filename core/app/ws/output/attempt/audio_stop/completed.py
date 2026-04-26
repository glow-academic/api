"""Output: attempt.chat.voice_ended (forward → connected clients).

Paired with audio_start/completed.py — relays the renamed
``attempt.chat.voice_ended`` internal-bus event to SIO rooms so the
client's voice teardown path fires when ``audio_stop_impl`` finishes.
The legacy ``attempt.audio_stop.completed`` name was retired with the
chat→voice migration.
"""

from typing import Any

from app.infra.globals import get_internal_sio, sio

internal_sio = get_internal_sio()


@internal_sio.on("attempt.chat.voice_ended")  # type: ignore
async def chat_voice_ended(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    for room in rooms:
        await sio.emit("attempt.chat.voice_ended", data, room=room)
