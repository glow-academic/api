"""GET /scenario/watch — live SSE endpoint (replaces /scenario/stream).

This is the long-lived connection for browsers (``EventSource``). The
``GET + SSE`` shape is fixed at the HTTP boundary because that's the
only transport ``EventSource`` understands.

LLM tools do NOT use this route. ``Scenario_Watch`` dispatches through
``INFRA_OPS`` straight to ``watch_scenario_impl`` (one-shot,
``WatchApiResponse``-returning sibling living at
``app.infra.scenario.watch``). Same event hub, two consumers:
this route streams; the impl snapshots-or-blocks.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.infra.globals import get_pool, get_redis_client
from app.infra.scenario.stream import stream_scenario_impl

router = APIRouter()


@router.get("/watch")
async def scenario_watch(
    http_request: Request,
    group_id: UUID | None = Query(default=None),
    run_id: UUID | None = Query(
        default=None,
        description=(
            "Optional run filter. If provided, only events whose envelope "
            "run_id matches are streamed — useful for per-run live feeds. "
            "Omit to receive every scenario event in the group (the FE "
            "default)."
        ),
    ),
) -> StreamingResponse:
    profile_id = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")
    session_id = getattr(http_request.state, "session_id", None)
    return await stream_scenario_impl(
        get_pool(), get_redis_client(),
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        run_id=run_id,
    )
