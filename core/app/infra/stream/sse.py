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

# Run-level terminal events that close a *run-scoped* stream. Deliberately
# STRICTER than infra/_watch.py's ``_is_terminal``: the generation lifecycle
# emits mid-run ``call.complete`` / ``text.complete`` frames (suffix
# ``.complete`` — no trailing "d"), and matching those would close the stream
# after the first tool call. We only close on the run's final frame:
#   - ``<artifact>.generate.completed`` / ``.failed`` / ``.error`` (the audited
#     run terminal, see ws/output.py + run_complete_impl), and
#   - ``…agent_completed`` / ``…media_complete`` / ``…media_error`` — the last
#     frame agent/media runs emit over the SSE bus. These are matched by
#     SUFFIX, not equality: the event_type is fully-qualified
#     (``persona.generate.agent_completed``), not the bare token.
_RUN_TERMINAL_SUFFIXES = (
    ".completed",
    ".failed",
    ".error",
    "agent_completed",
    "media_complete",
    "media_error",
)


def _is_run_terminal(event_type: str) -> bool:
    return (event_type or "").endswith(_RUN_TERMINAL_SUFFIXES)


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
                if run_id is not None and event.run_id != run_id:
                    continue

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
