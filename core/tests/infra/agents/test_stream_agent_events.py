"""Tests for stream_agent_events — streaming event parsing with callbacks."""

import json
from dataclasses import dataclass
from typing import Any

import pytest

from app.infra.agents.stream_agent_events import (
    StreamEventCallbacks,
    ToolCallState,
    stream_agent_events,
)

pytestmark = pytest.mark.asyncio


# ---------- ToolCallState ----------


async def test_tool_call_state_initial_values():
    state = ToolCallState(tool_call_id="tc_1", call_id="call_1")
    assert state.tool_call_id == "tc_1"
    assert state.call_id == "call_1"
    assert state.tool_name is None
    assert state.arguments_raw == ""
    assert state.completed is False


async def test_tool_call_state_accumulates_arguments():
    state = ToolCallState(tool_call_id="tc_1")
    state.arguments_raw += '{"ke'
    state.arguments_raw += 'y": "value"}'
    parsed = json.loads(state.arguments_raw)
    assert parsed == {"key": "value"}


# ---------- StreamEventCallbacks ----------


async def test_callbacks_default_to_none():
    callbacks = StreamEventCallbacks()
    assert callbacks.on_tool_call_start is None
    assert callbacks.on_tool_call_progress is None
    assert callbacks.on_tool_call_complete is None


# ---------- stream_agent_events ----------


@dataclass
class _FakeItem:
    type: str = "function_call"
    id: str = "item_1"
    name: str = "my_tool"
    call_id: str = "call_1"


@dataclass
class _FakeEventData:
    type: str = ""
    item: Any = None
    item_id: str | None = None
    call_id: str | None = None
    delta: str | None = None


@dataclass
class _FakeEvent:
    type: str = "raw_response_event"
    data: Any = None


class _FakeRunner:
    """Simulate a Runner that yields stream events."""

    def __init__(self, events: list):
        self._events = events

    async def stream_events(self):
        for e in self._events:
            yield e


async def test_stream_tool_call_start_callback():
    started = []

    async def on_start(tool_call_id, tool_name, call_id):
        started.append((tool_call_id, tool_name, call_id))

    item = _FakeItem()
    event_data = _FakeEventData(
        type="response.output_item.added",
        item=item,
    )
    event = _FakeEvent(data=event_data)

    runner = _FakeRunner([event])
    callbacks = StreamEventCallbacks(on_tool_call_start=on_start)
    await stream_agent_events(runner, callbacks)

    assert len(started) == 1
    assert started[0][1] == "my_tool"
    assert started[0][2] == "call_1"


async def test_stream_argument_delta_callback():
    deltas = []

    async def on_progress(tool_call_id, arguments_delta):
        deltas.append(arguments_delta)

    # First event: tool call start
    start_data = _FakeEventData(
        type="response.output_item.added",
        item=_FakeItem(),
    )
    # Second event: argument delta
    delta_data = _FakeEventData(
        type="response.function_call_arguments.delta",
        call_id="call_1",
        delta='{"key": "value"}',
    )

    runner = _FakeRunner([_FakeEvent(data=start_data), _FakeEvent(data=delta_data)])
    callbacks = StreamEventCallbacks(on_tool_call_progress=on_progress)
    await stream_agent_events(runner, callbacks)

    assert len(deltas) == 1
    assert deltas[0] == '{"key": "value"}'


async def test_stream_tool_call_complete_callback():
    completed = []

    async def on_complete(tool_call_id, final_args):
        completed.append((tool_call_id, final_args))

    start_data = _FakeEventData(
        type="response.output_item.added",
        item=_FakeItem(),
    )
    delta_data = _FakeEventData(
        type="response.function_call_arguments.delta",
        call_id="call_1",
        delta='{"result": 42}',
    )
    done_item = _FakeItem()
    done_data = _FakeEventData(
        type="response.output_item.done",
        item=done_item,
        item_id="item_1",
        call_id="call_1",
    )

    runner = _FakeRunner([
        _FakeEvent(data=start_data),
        _FakeEvent(data=delta_data),
        _FakeEvent(data=done_data),
    ])
    callbacks = StreamEventCallbacks(on_tool_call_complete=on_complete)
    await stream_agent_events(runner, callbacks)

    assert len(completed) == 1
    assert completed[0][1] == {"result": 42}


async def test_stream_skips_non_raw_response_events():
    started = []

    async def on_start(tool_call_id, tool_name, call_id):
        started.append(tool_call_id)

    # Event with wrong type should be skipped
    wrong_event = _FakeEvent()
    wrong_event.type = "some_other_type"

    runner = _FakeRunner([wrong_event])
    callbacks = StreamEventCallbacks(on_tool_call_start=on_start)
    await stream_agent_events(runner, callbacks)

    assert len(started) == 0
