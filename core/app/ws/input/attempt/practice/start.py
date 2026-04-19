"""Input: attempt.practice.start — DEPRECATED. Use POST /attempt/start."""

from typing import Any

from app.infra.globals import sio


@sio.on("attempt.practice.start")  # type: ignore
async def attempt_practice_start(sid: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"error": "Use POST /attempt/start instead"}
