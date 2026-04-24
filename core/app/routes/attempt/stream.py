"""Attempt stream — parameterless SSE endpoint.

GET /attempt/stream — delivers events for all groups the caller has joined,
filtered to artifact="attempt". Thin route; all logic lives in
`app.infra.attempt.stream.stream_attempt_impl`.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.infra.attempt.stream import stream_attempt_impl

router = APIRouter()


@router.get("/stream")
async def attempt_stream(http_request: Request) -> StreamingResponse:
    profile_id_raw = getattr(http_request.state, "profile_id", None)
    if not profile_id_raw:
        raise HTTPException(status_code=401, detail="Profile ID is required.")
    return await stream_attempt_impl(profile_id=str(profile_id_raw))
