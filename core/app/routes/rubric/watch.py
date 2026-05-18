"""GET /rubric/watch — live SSE endpoint (replaces /rubric/stream).

GET + SSE is fixed at the HTTP boundary so browser ``EventSource`` works.
LLM tools dispatch to ``watch_rubric_impl`` (one-shot) via INFRA_OPS, not
through this route. Same event hub feeds both consumers.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.infra.globals import get_pool, get_redis_client
from app.infra.rubric.stream import stream_rubric_impl

router = APIRouter()


@router.get("/watch")
async def rubric_watch(
    http_request: Request,
    group_id: UUID | None = Query(default=None),
    run_id: UUID | None = Query(
        default=None,
        description=(
            "Optional run filter. If provided, only events whose envelope "
            "run_id matches are streamed. Omit to receive every rubric event "
            "in the group (the FE default)."
        ),
    ),
) -> StreamingResponse:
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")
    session_id = getattr(http_request.state, "session_id", None)
    return await stream_rubric_impl(
        get_pool(), get_redis_client(),
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        run_id=run_id,
    )
