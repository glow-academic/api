"""Tests for RealtimeAudioAdapter — provider-generic Realtime API adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.infra.websocket.adapters.audio.realtime import (
    DEFAULT_REALTIME_MODEL,
    DEFAULT_REALTIME_URL,
    RealtimeAudioAdapter,
)

pytestmark = pytest.mark.asyncio


async def test_default_constants():
    """Default URL and model constants are set correctly."""
    assert "api.openai.com" in DEFAULT_REALTIME_URL
    assert "realtime" in DEFAULT_REALTIME_MODEL


async def test_implementation_type_is_websocket():
    """RealtimeAudioAdapter reports 'websocket' implementation type."""
    emitter = AsyncMock()
    adapter = RealtimeAudioAdapter(emitter)

    assert adapter.get_implementation_type() == "websocket"


async def test_format_tools_passes_through_function_type():
    """Tools already in function format are passed through."""
    emitter = AsyncMock()
    adapter = RealtimeAudioAdapter(emitter)

    tools = [
        {"type": "function", "name": "search", "parameters": {}}
    ]
    result = adapter._format_tools(tools)

    assert len(result) == 1
    assert result[0]["type"] == "function"
    assert result[0]["name"] == "search"


async def test_format_tools_converts_chat_completions_format():
    """Tools in Chat Completions format are converted to Realtime format."""
    emitter = AsyncMock()
    adapter = RealtimeAudioAdapter(emitter)

    tools = [
        {
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {"type": "object", "properties": {}},
            }
        }
    ]
    result = adapter._format_tools(tools)

    assert len(result) == 1
    assert result[0]["type"] == "function"
    assert result[0]["name"] == "get_weather"
    assert result[0]["description"] == "Get weather for a location"


async def test_format_tools_handles_empty_list():
    """Empty tools list returns empty list."""
    emitter = AsyncMock()
    adapter = RealtimeAudioAdapter(emitter)

    result = adapter._format_tools([])
    assert result == []


async def test_stop_session_cancels_tasks():
    """stop_session cancels uplink/downlink tasks and closes WS."""
    import asyncio

    emitter = AsyncMock()
    adapter = RealtimeAudioAdapter(emitter)

    from app.infra.websocket.session_store import AudioSession

    session = AudioSession(
        sid="test-sid",
        chat_id="test-chat",
        run_id="test-run",
        group_id="test-group",
    )

    # Create fake tasks
    async def noop():
        await asyncio.sleep(100)

    task1 = asyncio.create_task(noop())
    task2 = asyncio.create_task(noop())
    adapter._tasks["test-group"] = [task1, task2]

    mock_ws = AsyncMock()
    session.oa_ws_connection = mock_ws

    await adapter.stop_session(session)

    assert task1.cancelled()
    assert task2.cancelled()
    mock_ws.close.assert_called_once()
    assert session.oa_ws_connection is None
    assert "test-group" not in adapter._tasks
