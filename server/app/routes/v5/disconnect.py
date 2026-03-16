"""Stream disconnect endpoint — POST /v5/disconnect.

Destroys a stream session and cleans up all joined entities.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.stream.session import destroy_session, get_session_profile

router = APIRouter()


class DisconnectRequest(BaseModel):
    sid: str


class DisconnectResponse(BaseModel):
    success: bool


@router.post("/disconnect", response_model=DisconnectResponse)
async def disconnect(
    request: DisconnectRequest,
    http_request: Request,
) -> DisconnectResponse:
    """Destroy a stream session."""
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")

    session_profile = await get_session_profile(request.sid)
    if not session_profile or session_profile != profile_id:
        raise HTTPException(status_code=403, detail="Session not found or not owned.")

    await destroy_session(request.sid)
    return DisconnectResponse(success=True)
