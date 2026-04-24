"""Shared helper for per-artifact SSE streams.

All per-artifact `stream_{artifact}_impl` functions delegate here. Keeps the
multi-queue wait / keepalive / framing / cleanup logic in one place while
each artifact keeps its own canonical impl as a stable named entry point
(for tool calling, codegen, and replication).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.infra.stream.hub import subscribe, unsubscribe
from app.infra.stream.session import get_joined_groups

DEFAULT_KEEPALIVE_SEC = 15.0


async def build_artifact_stream_impl(
    *,
    profile_id: str,
    artifact: str,
    keepalive_sec: float = DEFAULT_KEEPALIVE_SEC,
) -> StreamingResponse:
    """Build an SSE StreamingResponse scoped to `artifact` for `profile_id`.

    Subscribes to every group the profile has joined, filters the live event
    stream to only events where `event.artifact == artifact`, and yields SSE
    frames until the client disconnects. Non-matching events on the same
    group queues are silently dropped — filtering is server-side so clients
    don't pay for events they didn't subscribe to.
    """
    joined_groups = await get_joined_groups(profile_id)
    if not joined_groups:
        raise HTTPException(
            status_code=400,
            detail="No groups joined. Call /attempt/join first.",
        )

    queues = [subscribe(group_id=g) for g in joined_groups]

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
                        timeout=keepalive_sec,
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
                    if event.artifact != artifact:
                        continue
                    yield f"event: {event.event_type}\n"
                    yield f"data: {event.model_dump_json()}\n\n"
        finally:
            for q in queues:
                unsubscribe(q)

    return StreamingResponse(_gen(), media_type="text/event-stream")
