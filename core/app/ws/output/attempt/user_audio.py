"""Output: attempt.chat.user_audio

Emitted by the realtime audio adapter on ``speech_stopped``. Carries the
resource-level ``audios_id`` of the captured user speech — the full
audio chain (upload + resource + entry + junctions) is already created,
so the client can go straight to STT + chat_message.
"""

import logging
from typing import Any

from app.infra.globals import get_internal_sio, sio

logger = logging.getLogger(__name__)

internal_sio = get_internal_sio()


@internal_sio.on("attempt.chat.user_audio")  # type: ignore
async def attempt_chat_user_audio_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    rooms = data.get("rooms") or ([sid] if sid else [])
    logger.info(
        f"VOICE_TRACE[1] user_audio fwd: sid={sid!r} rooms={rooms} "
        f"group_id={data.get('group_id')} audios_id={data.get('audios_id')}"
    )
    for room in rooms:
        await sio.emit("attempt.chat.user_audio", data, room=room)
