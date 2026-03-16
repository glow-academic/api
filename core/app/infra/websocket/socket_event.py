"""SocketEvent — pure data container for deferred WebSocket emission.

Canonical pattern: business logic functions accept ``emit: EmitFn`` as a
parameter and call ``await emit([...events])`` to produce events.  The
function never knows about sockets, SSE, or any transport — the **caller**
decides what ``emit`` does by providing the implementation.

Production: ``emit = make_emit()`` → wraps ``flush_events``.
Tests:      ``emit, events = recording_emit()`` → spy/recorder.

Two buses:
  - "client"   → sio.emit (client-facing namespace)
  - "internal" → internal_sio.emit (server-to-server namespace)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol


class AsyncEmitter(Protocol):
    """Minimal interface for a socket emitter (sio or internal_sio)."""

    async def emit(self, event: str, data: Any, **kwargs: Any) -> None: ...


# Type alias for emit callback — every business logic function accepts this.
# Production: make_emit(). Tests: recording_emit().
EmitFn = Callable[[list["SocketEvent"]], Awaitable[None]]


@dataclass(frozen=True)
class SocketEvent:
    """A deferred WebSocket event ready for emission."""

    bus: str  # "client" | "internal"
    event: str  # event name, e.g. "generation_started"
    data: dict[str, Any]  # serialized payload (already model_dump'd)
    sid: str | None = None  # routing: socket ID
    room: str | None = None  # routing: room name (client bus only)


def client_event(
    event: str,
    data: dict[str, Any],
    *,
    room: str | None = None,
) -> SocketEvent:
    """Build a client-bus event."""
    return SocketEvent(bus="client", event=event, data=data, room=room)


def internal_event(
    event: str,
    data: dict[str, Any],
    *,
    sid: str | None = None,
) -> SocketEvent:
    """Build an internal-bus event."""
    return SocketEvent(bus="internal", event=event, data=data, sid=sid)


async def flush_events(
    events: list[SocketEvent],
    *,
    client_sio: AsyncEmitter | None = None,
    internal_sio: AsyncEmitter | None = None,
) -> None:
    """Emit a list of SocketEvents to their respective buses.

    This is the single I/O boundary — everything before this is pure.

    When called without explicit emitters, resolves them from globals
    (production path). Pass explicit emitters for testing.
    """
    if client_sio is None or internal_sio is None:
        from app.infra.globals import get_internal_sio, sio

        if client_sio is None:
            client_sio = sio
        if internal_sio is None:
            internal_sio = get_internal_sio()

    for e in events:
        if e.bus == "client":
            await client_sio.emit(e.event, e.data, room=e.room or "")
        elif e.bus == "internal":
            await internal_sio.emit(e.event, e.data)
        else:
            raise ValueError(f"Unknown bus: {e.bus}")


# ═══════════════════════════════════════════════════════════════════════════
# EmitFn factories — production and test
# ═══════════════════════════════════════════════════════════════════════════


def make_emit(
    *,
    client_sio: AsyncEmitter | None = None,
    internal_sio: AsyncEmitter | None = None,
) -> EmitFn:
    """Create a production EmitFn that wraps flush_events.

    Usage in a thin socket handler::

        @internal_sio.on("some_event")
        async def handler(data):
            await some_business_logic(data, emit=make_emit())
    """

    async def _emit(events: list[SocketEvent]) -> None:
        await flush_events(events, client_sio=client_sio, internal_sio=internal_sio)

    return _emit


def recording_emit() -> tuple[EmitFn, list[SocketEvent]]:
    """Create a test EmitFn that records all events.

    Returns (emit_fn, recorded_events) — assert against the list.

    Usage in tests::

        emit, events = recording_emit()
        await some_business_logic(data, emit=emit)
        assert len(events) == 2
        assert events[0].event == "generation_started"
    """
    recorded: list[SocketEvent] = []

    async def _emit(events: list[SocketEvent]) -> None:
        recorded.extend(events)

    return _emit, recorded
