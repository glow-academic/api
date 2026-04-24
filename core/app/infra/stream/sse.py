"""Shared helpers for per-artifact SSE streams.

Two shapes, matching the two group-scoping patterns in the codebase:

- ``build_artifact_stream_impl`` — single time-windowed group, filtered to
  one artifact. Used by persona, scenario, cohort, etc. — artifacts that
  resolve exactly one group per (profile, session) via ``group_{artifact}_impl``.

- ``build_joined_stream_impl`` — multi-queue across every group the profile
  has joined (``get_joined_groups``), no artifact filter. Used by ``attempt``,
  whose semantics are explicit join/leave into many rooms and whose events
  span multiple artifact types during a chat flow.

Per-artifact ``stream_{artifact}_impl`` functions delegate to whichever
helper matches the artifact's group model. The impls remain the canonical
named entry points for tool calling / codegen / replication.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.infra.stream.hub import subscribe, unsubscribe
from app.infra.stream.session import get_joined_groups

DEFAULT_KEEPALIVE_SEC = 15.0


async def build_artifact_stream_impl(
    *,
    group_id: UUID,
    artifact: str,
    keepalive_sec: float = DEFAULT_KEEPALIVE_SEC,
) -> StreamingResponse:
    """SSE stream for a single time-windowed group, filtered to one artifact.

    Canonical path for per-artifact streams — the caller resolves ``group_id``
    via ``group_{artifact}_impl`` and passes it here. Events on the group
    whose ``artifact`` field doesn't match are silently dropped.
    """
    queue = subscribe(group_id=group_id)

    async def _gen() -> AsyncIterator[str]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=keepalive_sec
                    )
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue

                if event.artifact != artifact:
                    continue

                yield f"event: {event.event_type}\n"
                yield f"data: {event.model_dump_json()}\n\n"
        finally:
            unsubscribe(queue)

    return StreamingResponse(_gen(), media_type="text/event-stream")


async def build_joined_stream_impl(
    *,
    profile_id: str,
    keepalive_sec: float = DEFAULT_KEEPALIVE_SEC,
) -> StreamingResponse:
    """SSE stream across every group the profile has joined. No artifact filter.

    Used by ``attempt`` — its events span persona/rubric/etc. during a chat,
    and its group model is explicit join/leave into many rooms rather than a
    single time-windowed group.
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
                    yield f"event: {event.event_type}\n"
                    yield f"data: {event.model_dump_json()}\n\n"
        finally:
            for q in queues:
                unsubscribe(q)

    return StreamingResponse(_gen(), media_type="text/event-stream")
