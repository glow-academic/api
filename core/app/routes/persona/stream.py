"""Persona stream — parameterless SSE endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.infra.globals import get_pool, get_redis_client
from app.infra.persona.stream import stream_persona_impl

router = APIRouter()


@router.get("/stream")
async def persona_stream(http_request: Request) -> StreamingResponse:
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")
    session_id = getattr(http_request.state, "session_id", None)
    return await stream_persona_impl(
        get_pool(), get_redis_client(),
        profile_id=profile_id,
        session_id=session_id,
    )
