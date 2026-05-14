"""Input: attempt.chat.grade — DEPRECATED.

Grading now goes through /attempt/generate with operations: ["chat_grade"].
This handler is kept as a no-op for backward compatibility with old clients
that still emit the attempt.chat.grade WebSocket event.
"""

from typing import Any

from app.infra.globals import sio


@sio.on("attempt.chat_grade")  # type: ignore
async def attempt_grade(sid: str, data: dict[str, Any]) -> None:
    # No-op: grading is now triggered via /attempt/generate
    pass
