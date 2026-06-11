"""Shared API types for centralized event delivery."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# Run-level terminal event suffixes — the final frame a run-scoped SSE stream
# (``glow … watch <run_id>``) closes on. Shared so the hub (which must never
# DROP one of these on a full-queue shed — S4) and the SSE generator (which
# closes the stream on one) agree on exactly what "terminal" means. Matched by
# SUFFIX: event_type is fully-qualified (``persona.generate.completed``), and
# mid-run ``.complete`` (no trailing "d") frames must NOT match.
RUN_TERMINAL_SUFFIXES: tuple[str, ...] = (
    ".completed",
    ".failed",
    ".error",
    "agent_completed",
    "media_complete",
    "media_error",
)


def is_run_terminal(event_type: str) -> bool:
    """True when ``event_type`` is a run's final frame (see RUN_TERMINAL_SUFFIXES)."""
    return (event_type or "").endswith(RUN_TERMINAL_SUFFIXES)


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
