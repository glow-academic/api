"""Attempt stream — parameterless SSE endpoint.

GET /attempt/stream — delivers events for all groups the caller has joined.
No sid, no entity subscriptions. Just auth + joined groups.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.infra.stream.hub import subscribe, unsubscribe
from app.infra.stream.session import get_joined_groups

router = APIRouter()


@router.get("/stream")
async def attempt_stream(
    http_request: Request,
) -> StreamingResponse:
    """Stream events for all joined groups via SSE."""
    profile_id_raw = getattr(http_request.state, "profile_id", None)
    if not profile_id_raw:
        raise HTTPException(status_code=401, detail="Profile ID is required.")

    profile_id = str(profile_id_raw)

    # Get all groups this profile has joined
    joined_groups = await get_joined_groups(profile_id)
    if not joined_groups:
        raise HTTPException(
            status_code=400,
            detail="No groups joined. Call /attempt/join first.",
        )

    # Subscribe to live events for each joined group
    queues = []
    for group_id in joined_groups:
        queue = subscribe(group_id=group_id)
        queues.append(queue)

    async def _gen() -> AsyncIterator[str]:
        try:
            while True:
                done: set = set()
                try:
                    wait_tasks = [
                        asyncio.ensure_future(q.get()) for q in queues
                    ]
                    done, pending = await asyncio.wait(
                        wait_tasks,
                        timeout=15.0,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in pending:
                        task.cancel()
                except TimeoutError:
                    pass

                if not done:
                    yield ": keep-alive\n\n"
                    continue

                for task in done:
                    event = task.result()
                    yield f"event: {event.event_type}\n"
                    yield f"data: {event.model_dump_json()}\n\n"
        finally:
            for q in queues:
                unsubscribe(q)

    return StreamingResponse(_gen(), media_type="text/event-stream")
