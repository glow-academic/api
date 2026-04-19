"""Input: attempt.start — DEPRECATED.

Attempt start now uses POST /attempt/start.
This handler is kept as a no-op for backward compatibility.
"""

from typing import Any

from app.infra.globals import sio


@sio.on("attempt.start")  # type: ignore
async def attempt_start(sid: str, data: dict[str, Any]) -> None:
    # No-op: use POST /attempt/start instead
    pass
