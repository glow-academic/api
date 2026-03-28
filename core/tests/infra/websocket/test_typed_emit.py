"""Tests for typed websocket emit helpers."""

import pytest
from pydantic import BaseModel

import app.infra.websocket.typed_emit as typed_emit_mod


class DemoPayload(BaseModel):
    id: str
    count: int


class RecordingClientSio:
    def __init__(self):
        self.calls: list[tuple[str, dict, str]] = []

    async def emit(self, event_name: str, payload: dict, room: str = "") -> None:
        self.calls.append((event_name, payload, room))


class RecordingInternalBus:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def emit(self, event_name: str, payload: dict) -> None:
        self.calls.append((event_name, payload))


class TestEmitToClient:
    @pytest.mark.asyncio
    async def test_emits_model_dump_json_payload(self):
        sio = RecordingClientSio()

        await typed_emit_mod.emit_to_client(
            "generation_complete",
            DemoPayload(id="abc", count=3),
            room="sid-1",
            sio_client=sio,
        )

        assert sio.calls == [
            ("generation_complete", {"id": "abc", "count": 3}, "sid-1")
        ]

    @pytest.mark.asyncio
    async def test_defaults_room_to_empty_string(self):
        sio = RecordingClientSio()

        await typed_emit_mod.emit_to_client(
            "generation_complete",
            DemoPayload(id="a", count=1),
            sio_client=sio,
        )

        assert sio.calls == [("generation_complete", {"id": "a", "count": 1}, "")]


class TestEmitToInternal:
    @pytest.mark.asyncio
    async def test_emits_payload_with_sid_and_group_id(self):
        bus = RecordingInternalBus()

        await typed_emit_mod.emit_to_internal(
            "generation_complete",
            DemoPayload(id="abc", count=3),
            sid="sid-1",
            group_id="group-1",
            internal_bus=bus,
        )

        assert bus.calls == [
            (
                "generation_complete",
                {
                    "id": "abc",
                    "count": 3,
                    "sid": "sid-1",
                    "group_id": "group-1",
                },
            )
        ]

    @pytest.mark.asyncio
    async def test_omits_optional_fields_when_not_provided(self):
        bus = RecordingInternalBus()

        await typed_emit_mod.emit_to_internal(
            "generation_complete",
            DemoPayload(id="abc", count=3),
            internal_bus=bus,
        )

        assert bus.calls == [("generation_complete", {"id": "abc", "count": 3})]
