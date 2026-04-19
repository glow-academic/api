"""Stop — cancel an active generation by group_id.

Root-level transport route (like stream.py). No DB connection needed.
Cancels the active Runner result and sets the Redis cancel flag.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.websocket.cancel_active_result import cancel_active_result
from app.infra.websocket.cancel_active_run import cancel_active_run

router = APIRouter()


class StopRequest(BaseModel):
    group_id: UUID


class StopResponse(BaseModel):
    success: bool


@router.post("/stop", response_model=StopResponse)
async def stop_generation(
    request: StopRequest,
    http_request: Request,
) -> StopResponse:
    """Cancel an active generation by group_id."""
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Missing profile")

    group_id = str(request.group_id)

    # Cancel local Runner result (immediate — stops token streaming)
    await cancel_active_result(group_id)

    # Set Redis cancel flag (cooperative — stops upstream/parallel workers)
    await cancel_active_run(group_id)

    return StopResponse(success=True)
