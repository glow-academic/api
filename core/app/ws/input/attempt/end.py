"""Input: attempt.chat.end — DEPRECATED.

Chat ending now uses /attempt/chat/complete + /attempt/complete primitives.
This handler is kept as a no-op for backward compatibility.
"""

from typing import Any

from app.infra.globals import sio


@sio.on("attempt.chat.end")  # type: ignore
async def attempt_end(sid: str, data: dict[str, Any]) -> None:
    # No-op: use /attempt/chat/complete + /attempt/complete instead
    pass
