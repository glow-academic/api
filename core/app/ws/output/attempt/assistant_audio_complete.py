"""Output: attempt.chat.assistant_audio.complete

Fired once per assistant turn after the realtime adapter flushes the
accumulated PCM through the canonical audio upload chain. Carries the
resource-level ``audios_id`` so the client can attach the full clip to
the assistant's chat message. Per-frame playback bytes stream separately
via ``attempt.chat.assistant_audio``.
"""

from typing import Any

from app.infra.globals import get_internal_sio, sio

internal_sio = get_internal_sio()


@internal_sio.on("attempt.chat.assistant_audio.complete")  # type: ignore
async def attempt_chat_assistant_audio_complete_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    for room in rooms:
        await sio.emit("attempt.chat.assistant_audio.complete", data, room=room)
