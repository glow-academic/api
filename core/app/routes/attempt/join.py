"""Attempt join — subscribe to events for a group.

POST /attempt/join { group_id }
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.globals import get_redis_client
from app.infra.stream.session import join_group

router = APIRouter()


class AttemptJoinRequest(BaseModel):
    group_id: UUID


class AttemptJoinResponse(BaseModel):
    success: bool
    group_id: str


@router.post("/join", response_model=AttemptJoinResponse)
async def attempt_join(
    request: AttemptJoinRequest,
    http_request: Request,
) -> AttemptJoinResponse:
    """Subscribe to events for a group."""
    profile_id: UUID | None = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")

    await join_group(str(profile_id), request.group_id)
    return AttemptJoinResponse(success=True, group_id=str(request.group_id))
