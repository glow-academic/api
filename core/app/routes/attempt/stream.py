"""Attempt stream — per-(artifact, group_id) SSE endpoint."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.infra.attempt.stream import stream_attempt_impl

router = APIRouter()


@router.get("/stream")
async def attempt_stream(
    http_request: Request,
    group_id: UUID | None = Query(default=None),
) -> StreamingResponse:
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")
    return await stream_attempt_impl(profile_id=str(profile_id), group_id=group_id)
