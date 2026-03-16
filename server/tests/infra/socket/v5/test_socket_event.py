"""Tests for infra.websocket.socket_event using simple recording emitters."""

import pytest

from app.infra.websocket.socket_event import (
    SocketEvent,
    client_event,
    flush_events,
    internal_event,
    make_emit,
    recording_emit,
)


class RecorderEmitter:
    def __init__(self):
        self.calls: list[tuple[str, dict, dict]] = []

    async def emit(self, event: str, data, **kwargs) -> None:
        self.calls.append((event, data, kwargs))


# ═══════════════════════════════════════════════════════════════════════════
# SocketEvent construction — pure unit tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSocketEventConstruction:
    def test_client_event_defaults(self):
        e = client_event("generation_started", {"run_id": "abc"})
        assert e.bus == "client"
        assert e.event == "generation_started"
        assert e.data == {"run_id": "abc"}
        assert e.room is None
        assert e.sid is None

    def test_client_event_with_room(self):
        e = client_event("progress", {"pct": 50}, room="sid-123")
        assert e.room == "sid-123"

    def test_internal_event_defaults(self):
        e = internal_event("generate_artifact", {"agent_id": "x"})
        assert e.bus == "internal"
        assert e.event == "generate_artifact"
        assert e.data == {"agent_id": "x"}
        assert e.sid is None
        assert e.room is None

    def test_internal_event_with_sid(self):
        e = internal_event("generate_artifact", {"agent_id": "x"}, sid="sid-456")
        assert e.sid == "sid-456"

    def test_frozen(self):
        e = client_event("test", {})
        with pytest.raises(AttributeError):
            e.bus = "internal"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════
# flush_events — DI-based tests (no patching needed)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestFlushEvents:
    async def test_empty_list_does_nothing(self):
        """No events → no emit calls."""
        client = RecorderEmitter()
        internal = RecorderEmitter()
        await flush_events([], client_sio=client, internal_sio=internal)
        assert client.calls == []
        assert internal.calls == []

    async def test_client_event_emits_to_sio(self):
        e = client_event("gen_complete", {"id": "1"}, room="room-1")
        client = RecorderEmitter()
        internal = RecorderEmitter()
        await flush_events([e], client_sio=client, internal_sio=internal)

        assert client.calls == [("gen_complete", {"id": "1"}, {"room": "room-1"})]
        assert internal.calls == []

    async def test_client_event_room_defaults_to_empty(self):
        e = client_event("test", {"x": 1})
        client = RecorderEmitter()
        await flush_events([e], client_sio=client, internal_sio=RecorderEmitter())

        assert client.calls == [("test", {"x": 1}, {"room": ""})]

    async def test_internal_event_emits_to_internal_sio(self):
        e = internal_event("generate_artifact", {"agent": "a"}, sid="sid-1")
        client = RecorderEmitter()
        internal = RecorderEmitter()
        await flush_events([e], client_sio=client, internal_sio=internal)

        assert internal.calls == [("generate_artifact", {"agent": "a"}, {})]
        assert client.calls == []

    async def test_mixed_events_emit_in_order(self):
        """Client and internal events interleaved — all emitted in order."""
        events = [
            client_event("started", {"a": 1}, room="r1"),
            internal_event("dispatch_1", {"b": 2}),
            internal_event("dispatch_2", {"c": 3}),
            client_event("done", {"d": 4}, room="r1"),
        ]

        client = RecorderEmitter()
        internal = RecorderEmitter()
        await flush_events(events, client_sio=client, internal_sio=internal)

        assert client.calls == [
            ("started", {"a": 1}, {"room": "r1"}),
            ("done", {"d": 4}, {"room": "r1"}),
        ]
        assert internal.calls == [
            ("dispatch_1", {"b": 2}, {}),
            ("dispatch_2", {"c": 3}, {}),
        ]

    async def test_unknown_bus_raises(self):
        e = SocketEvent(bus="unknown", event="x", data={})
        with pytest.raises(ValueError, match="Unknown bus: unknown"):
            await flush_events(
                [e],
                client_sio=RecorderEmitter(),
                internal_sio=RecorderEmitter(),
            )


# ═══════════════════════════════════════════════════════════════════════════
# make_emit — production EmitFn factory
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestMakeEmit:
    async def test_delegates_to_flush_events(self):
        """make_emit wraps flush_events with injected emitters."""
        client = RecorderEmitter()
        internal = RecorderEmitter()
        emit = make_emit(client_sio=client, internal_sio=internal)

        await emit(
            [
                client_event("started", {"a": 1}, room="r1"),
                internal_event("dispatch", {"b": 2}),
            ]
        )

        assert client.calls == [("started", {"a": 1}, {"room": "r1"})]
        assert internal.calls == [("dispatch", {"b": 2}, {})]

    async def test_multiple_calls_accumulate(self):
        """Calling emit multiple times works (streaming pattern)."""
        internal = RecorderEmitter()
        emit = make_emit(client_sio=RecorderEmitter(), internal_sio=internal)

        await emit([internal_event("progress", {"pct": 25})])
        await emit([internal_event("progress", {"pct": 50})])
        await emit([internal_event("complete", {"ok": True})])

        assert internal.calls == [
            ("progress", {"pct": 25}, {}),
            ("progress", {"pct": 50}, {}),
            ("complete", {"ok": True}, {}),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# recording_emit — test spy / recorder
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestRecordingEmit:
    async def test_captures_all_events(self):
        emit, events = recording_emit()

        await emit([internal_event("generation_started", {"run_id": "r1"})])
        await emit(
            [
                internal_event("generate_artifact", {"agent": "a1"}),
                internal_event("generate_artifact", {"agent": "a2"}),
            ]
        )

        assert len(events) == 3
        assert events[0].event == "generation_started"
        assert events[1].event == "generate_artifact"
        assert events[1].data == {"agent": "a1"}
        assert events[2].data == {"agent": "a2"}

    async def test_empty_emit_is_noop(self):
        emit, events = recording_emit()
        await emit([])
        assert events == []

    async def test_records_both_buses(self):
        emit, events = recording_emit()

        await emit(
            [
                client_event("user_progress", {"pct": 50}, room="r1"),
                internal_event("generation_channel", {"type": "complete"}),
            ]
        )

        assert events[0].bus == "client"
        assert events[0].room == "r1"
        assert events[1].bus == "internal"

    async def test_pattern_business_logic_with_emit(self):
        """Demonstrates the canonical pattern: function accepts emit, test records."""

        async def some_business_logic(
            data: dict,
            *,
            emit: ...,  # type: ignore[override]
        ) -> str:
            await emit([internal_event("step_1", {"input": data["x"]})])
            result = data["x"] * 2
            await emit([internal_event("step_2", {"result": result})])
            return str(result)

        emit, events = recording_emit()
        result = await some_business_logic({"x": 21}, emit=emit)

        assert result == "42"
        assert len(events) == 2
        assert events[0].event == "step_1"
        assert events[0].data == {"input": 21}
        assert events[1].event == "step_2"
        assert events[1].data == {"result": 42}
