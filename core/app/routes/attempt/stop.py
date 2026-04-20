"""Attempt stop — cancel an active generation.

POST /attempt/stop — cancel by group_id (will become run_id).
No DB connection needed.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.websocket.cancel_active_result import cancel_active_result
from app.infra.websocket.cancel_active_run import cancel_active_run
from app.infra.websocket.cancel_realtime_turn import cancel_realtime_turn

router = APIRouter()


class AttemptStopRequest(BaseModel):
    group_id: UUID


class AttemptStopResponse(BaseModel):
    success: bool


@router.post("/stop", response_model=AttemptStopResponse)
async def attempt_stop(
    request: AttemptStopRequest,
    http_request: Request,
) -> AttemptStopResponse:
    """Cancel an active generation by group_id."""
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Missing profile")

    group_id = str(request.group_id)

    await cancel_active_result(group_id)
    await cancel_active_run(group_id)
    # Realtime: cancel the current turn without closing the session so the
    # conversation can continue with the next /attempt/generate call.
    await cancel_realtime_turn(group_id)

    return AttemptStopResponse(success=True)
