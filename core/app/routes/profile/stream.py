"""Profile stream — parameterless SSE endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.infra.globals import get_pool, get_redis_client
from app.infra.profile.stream import stream_profile_impl

router = APIRouter()


@router.get("/stream")
async def profile_stream(http_request: Request) -> StreamingResponse:
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")
    session_id = getattr(http_request.state, "session_id", None)
    return await stream_profile_impl(
        get_pool(), get_redis_client(),
        profile_id=profile_id,
        session_id=session_id,
    )
