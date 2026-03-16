"""Input: attempt.audio_stop"""

from typing import Any

from app.infra.globals import sio
from app.infra.websocket.attempt.audio_stop import (
    attempt_audio_stop_internal_impl,
)


@sio.on("attempt.audio_stop")  # type: ignore
async def attempt_audio_stop(sid: str, data: dict[str, Any]) -> None:
    chat_id = data.get("chat_id")
    if not chat_id:
        return

    try:
        await attempt_audio_stop_internal_impl({"chat_id": chat_id, "sid": sid})
    except ValueError:
        return
