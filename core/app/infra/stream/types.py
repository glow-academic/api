"""Shared API types for centralized event delivery."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# Run-level TERMINAL suffixes — the final frame a run-scoped SSE stream
# (``glow … watch <run_id>``) closes on. These are TRUE terminals only: the
# run is genuinely over. Matched by SUFFIX: event_type is fully-qualified
# (``persona.generate.completed``), and mid-run ``.complete`` (no trailing
# "d") frames must NOT match.
#
# ``media_complete``/``media_error`` stay here: media-only runs signal their
# completion via these (see ``_watch.py``), not via ``.completed``, so a
# run-scoped watcher must close on them.
#
# ``agent_completed`` was REMOVED (R5): it is a PER-AGENT progress milestone
# emitted (``execute.py``) BEFORE ``run_complete_impl`` persists and before the
# canonical ``.generate.completed``/``.failed``. Closing the run-scoped stream
# on it truncated single-agent watches and — worse — in a multi-agent run
# closed on the FIRST agent's ``agent_completed`` so the watcher never saw a
# sibling's ``.failed`` and reported phantom success, defeating the S1 fix for
# run-scoped consumers.
RUN_TERMINAL_SUFFIXES: tuple[str, ...] = (
    ".completed",
    ".failed",
    ".error",
    "media_complete",
    "media_error",
)

# Frames the hub must NEVER drop on a full-queue shed (S4): the true terminals
# above PLUS load-bearing progress milestones a consumer must still observe.
# ``agent_completed`` belongs here (a dropped per-agent milestone would leave a
# multi-agent UI with a missing agent) — but it must NOT close a run-scoped
# stream, which is why it lives here and not in RUN_TERMINAL_SUFFIXES.
NON_DROPPABLE_SUFFIXES: tuple[str, ...] = RUN_TERMINAL_SUFFIXES + (
    "agent_completed",
)


def is_run_terminal(event_type: str) -> bool:
    """True when ``event_type`` closes a run-scoped stream (a TRUE terminal)."""
    return (event_type or "").endswith(RUN_TERMINAL_SUFFIXES)


def is_non_droppable(event_type: str) -> bool:
    """True when the hub must never shed ``event_type`` on a full queue (S4).

    Broader than :func:`is_run_terminal` — includes progress milestones like
    ``agent_completed`` that must survive a shed but must NOT close a stream.
    """
    return (event_type or "").endswith(NON_DROPPABLE_SUFFIXES)


class EventEnvelope(BaseModel):
    """Transport-level event shape exposed by generic delivery endpoints."""

    id: str
    event_type: str
    artifact: str
    operation: str
    created_at: datetime
    group_id: UUID | None = None
    run_id: UUID | None = None
    entity_id: UUID | None = None
    call_id: UUID | None = None
    tool_id: UUID | None = None
    payload: dict = Field(default_factory=dict)
