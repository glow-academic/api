"""Input: attempt.stop — DEPRECATED.

Stop now uses POST /stop with group_id. No DB connection needed.
This handler is kept as a no-op for backward compatibility.
"""

from typing import Any

from app.infra.globals import sio


@sio.on("attempt.stop")  # type: ignore
async def attempt_stop(sid: str, data: dict[str, Any]) -> None:
    # No-op: use POST /stop instead
    pass
