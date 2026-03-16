"""Stream connect endpoint — POST /v5/connect.

Creates a stream session and returns an sid for use with SSE and join/leave.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.stream.session import create_session

router = APIRouter()


class ConnectResponse(BaseModel):
    sid: str


@router.post("/connect", response_model=ConnectResponse)
async def connect(http_request: Request) -> ConnectResponse:
    """Create a stream session for the authenticated profile."""
    profile_id: UUID | None = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(
            status_code=401,
            detail="Profile ID is required. Please sign in again.",
        )

    sid = await create_session(profile_id)
    return ConnectResponse(sid=sid)
