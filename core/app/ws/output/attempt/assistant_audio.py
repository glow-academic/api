"""Output: attempt.chat.assistant_audio

Emitted by the realtime audio adapter on ``response.audio.done``. Carries
the resource-level ``audios_id`` of the assistant's completed audio turn
so the client can attach it to the assistant's chat_message alongside
the transcript streamed via ``attempt.generate.text.complete``.
"""

from typing import Any

from app.infra.globals import get_internal_sio, sio

internal_sio = get_internal_sio()


@internal_sio.on("attempt.chat.assistant_audio")  # type: ignore
async def attempt_chat_assistant_audio_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    for room in rooms:
        await sio.emit("attempt.chat.assistant_audio", data, room=room)
