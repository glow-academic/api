"""GET /attempt/watch — live SSE endpoint (replaces /attempt/stream).

GET + SSE is fixed at the HTTP boundary so browser ``EventSource`` works.
LLM tools dispatch to ``watch_attempt_impl`` (one-shot) via INFRA_OPS, not
through this route. Same event hub feeds both consumers.

``group_id`` is required for this artifact (no resolver fallback).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.infra.attempt.stream import stream_attempt_impl

router = APIRouter()


@router.get("/watch")
async def attempt_watch(
    http_request: Request,
    group_id: UUID | None = Query(default=None),
    run_id: UUID | None = Query(
        default=None,
        description=(
            "Optional run filter. If provided, only events whose envelope "
            "run_id matches are streamed. Omit to receive every attempt event "
            "in the group (the FE default)."
        ),
    ),
) -> StreamingResponse:
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")
    return await stream_attempt_impl(
        profile_id=str(profile_id), group_id=group_id, run_id=run_id,
    )
