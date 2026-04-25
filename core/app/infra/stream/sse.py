"""Shared helpers for per-artifact SSE streams.

Single shape across the codebase:

- ``build_artifact_stream_impl`` — single time-windowed group, filtered to
  one artifact. Used by every artifact, including ``attempt``. The caller
  resolves ``group_id`` (via ``group_{artifact}_impl`` or by passing it
  through the route's ``?group_id=`` query param) and passes it here.

Per-artifact ``stream_{artifact}_impl`` functions delegate here. The impls
remain the canonical named entry points for tool calling / codegen /
replication.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi.responses import StreamingResponse

from app.infra.stream.hub import subscribe, unsubscribe

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
