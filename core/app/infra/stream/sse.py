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
from app.infra.stream.types import is_run_terminal as _is_run_terminal

DEFAULT_KEEPALIVE_SEC = 15.0

# Hard ceiling on a run-scoped stream's lifetime (S4). The run terminal frame
# normally closes the stream (see ``_is_run_terminal`` below); the hub now
# treats those frames as non-droppable so they reach the consumer. This timeout
# is the belt-and-suspenders fallback: if a terminal frame is STILL lost (the
# producer crashed before emitting it, a subscriber attached after it fired,
# etc.), a run-scoped watcher would otherwise loop on keep-alives forever. After
# this much idle time on a run-scoped stream we close it so the client gets a
# clean EOF and exits instead of hanging. Generous so a slow but live run is
# never cut off mid-flight; only a truly stuck/terminal-less stream hits it.
MAX_RUN_STREAM_IDLE_SEC = 600.0


async def build_artifact_stream_impl(
    *,
    group_id: UUID,
    artifact: str,
    run_id: UUID | None = None,
    keepalive_sec: float = DEFAULT_KEEPALIVE_SEC,
) -> StreamingResponse:
    """SSE stream for a single time-windowed group, filtered to one artifact.

    Canonical path for per-artifact streams — the caller resolves ``group_id``
    via ``group_{artifact}_impl`` and passes it here. Events on the group
    whose ``artifact`` field doesn't match are silently dropped.

    If ``run_id`` is provided, only events whose envelope ``run_id`` matches
    are yielded — useful when a caller wants a per-run live feed instead of
    the whole group. ``None`` (default) keeps current group-wide behavior.
    """
    queue = subscribe(group_id=group_id)

    async def _gen() -> AsyncIterator[str]:
        # Idle time accrued waiting for the next event on a run-scoped stream.
        # Reset whenever a matching event for this run is delivered; only pure
        # keep-alive ticks (no event) accumulate it. The fallback timeout (S4)
        # fires off this so a slow-but-live run that keeps emitting events for
        # this run_id never trips it — only a stream that goes terminal-less
        # idle does.
        idle_sec = 0.0
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=keepalive_sec
                    )
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    # S4 fallback: a run-scoped watcher whose terminal frame was
                    # lost (producer crash, dropped despite the hub's
                    # non-droppable guard, late attach) would otherwise loop on
                    # keep-alives forever. Cap the idle lifetime so it gets a
                    # clean EOF instead of hanging.
                    if run_id is not None:
                        idle_sec += keepalive_sec
                        if idle_sec >= MAX_RUN_STREAM_IDLE_SEC:
                            break
                    continue

                if event.artifact != artifact:
                    continue
                if run_id is not None and event.run_id != run_id:
                    continue

                # A real event for this run arrived → the stream is live; reset
                # the idle counter so the S4 fallback only fires on genuine
                # terminal-less silence, not on a busy run.
                idle_sec = 0.0

                # All events flow on the default ``message`` channel.
                # ``event_type`` lives inside the envelope payload so the
                # client multiplexer can dispatch (and wildcard-match) in
                # JS — the EventSource named-channel mechanism cannot.
                yield f"data: {event.model_dump_json()}\n\n"

                # Run-scoped watchers (``glow … watch <run_id>``) close on the
                # run's terminal frame so the client gets a clean EOF and exits
                # 0 instead of hanging on the open keep-alive loop. Group-wide
                # streams (run_id is None) stay open — a group feed is
                # intentionally long-lived.
                if run_id is not None and _is_run_terminal(event.event_type):
                    break
        finally:
            unsubscribe(queue)

    return StreamingResponse(_gen(), media_type="text/event-stream")
