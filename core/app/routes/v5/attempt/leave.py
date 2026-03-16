"""Attempt leave endpoint — POST /v5/attempt/leave.

Removes a chat entity from the caller's stream session.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.stream.session import get_session_profile, leave_entity

router = APIRouter()


class AttemptLeaveRequest(BaseModel):
    sid: str
    chat_id: UUID


class AttemptLeaveResponse(BaseModel):
    success: bool


@router.post("/leave", response_model=AttemptLeaveResponse)
async def attempt_leave(
    request: AttemptLeaveRequest,
    http_request: Request,
) -> AttemptLeaveResponse:
    """Leave a chat room, stopping real-time attempt updates."""
    profile_id: UUID | None = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")

    profile_id = UUID(str(profile_id))

    session_profile = await get_session_profile(request.sid)
    if not session_profile or session_profile != profile_id:
        raise HTTPException(status_code=403, detail="Session not found or not owned.")

    await leave_entity(request.sid, "attempt", request.chat_id)
    return AttemptLeaveResponse(success=True)
