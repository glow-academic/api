"""Attempt leave — unsubscribe from events for a group.

POST /attempt/leave { group_id }
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.stream.session import leave_group

router = APIRouter()


class AttemptLeaveRequest(BaseModel):
    group_id: UUID


class AttemptLeaveResponse(BaseModel):
    success: bool


@router.post("/leave", response_model=AttemptLeaveResponse)
async def attempt_leave(
    request: AttemptLeaveRequest,
    http_request: Request,
) -> AttemptLeaveResponse:
    """Unsubscribe from events for a group."""
    profile_id: UUID | None = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")

    await leave_group(str(profile_id), request.group_id)
    return AttemptLeaveResponse(success=True)
