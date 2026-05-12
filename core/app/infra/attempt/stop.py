"""Attempt stop — cancel an active generation.

Cancels in-flight realtime/result/run state for a given group_id.
Stateless (no DB connection); composes three websocket-cancel helpers.

Mirrors the routes/attempt/stop.py adapter — that route is now a thin
HTTP wrapper around stop_attempt_impl.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.infra.websocket.cancel_active_result import cancel_active_result
from app.infra.websocket.cancel_active_run import cancel_active_run
from app.infra.websocket.cancel_realtime_turn import cancel_realtime_turn


class AttemptStopRequest(BaseModel):
    group_id: UUID


class AttemptStopResponse(BaseModel):
    success: bool


async def stop_attempt_impl(
    *,
    profile_id: UUID,
    group_id: UUID,
) -> AttemptStopResponse:
    """Cancel an active generation by group_id.

    Cancels the active result-stream, the active run, and the in-flight
    realtime turn. Does not close the realtime session — the next
    ``/attempt/generate`` call can continue the conversation.

    Args:
        profile_id: Caller's profile UUID (unused today; kept for parity
            with the rest of the infra layer and for future audit).
        group_id: Chat group UUID identifying the conversation to cancel.

    Returns:
        ``AttemptStopResponse(success=True)`` once all three cancel calls
        complete (each is idempotent and silently no-ops if there is
        nothing active).
    """
    gid = str(group_id)
    await cancel_active_result(gid)
    await cancel_active_run(gid)
    await cancel_realtime_turn(gid)
    return AttemptStopResponse(success=True)
