"""Tests for audio_stop — internal impl for attempt audio stop."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.infra.websocket.attempt.audio_stop import (
    AudioStopInternalResult,
    attempt_audio_stop_internal_impl,
)

pytestmark = pytest.mark.asyncio


async def test_audio_stop_result_model_fields():
    """AudioStopInternalResult carries expected fields."""
    result = AudioStopInternalResult(chat_id="chat-1")

    assert result.chat_id == "chat-1"
    assert result.stopped is True


async def test_audio_stop_raises_without_chat_id():
    """attempt_audio_stop_internal_impl raises ValueError without chat_id."""
    with pytest.raises(ValueError, match="Missing chat_id"):
        await attempt_audio_stop_internal_impl({})


async def test_audio_stop_raises_when_no_session():
    """Raises ValueError when no active audio session exists for chat."""
    with patch(
        "app.infra.websocket.attempt.audio_stop.get_session_by_chat_id",
        return_value=None,
    ):
        with pytest.raises(ValueError, match="No active audio session"):
            await attempt_audio_stop_internal_impl(
                {"chat_id": str(uuid4())}
            )


async def test_audio_stop_emits_session_complete():
    """Successful stop emits generate_audio_session_complete event."""
    from app.infra.websocket.session_store import AudioSession

    session = AudioSession(
        sid="test-sid",
        chat_id="chat-stop",
        run_id="run-stop",
        group_id="group-stop",
        conversation_id=None,
    )

    mock_sio = AsyncMock()
    mock_pool = MagicMock()

    with patch(
        "app.infra.websocket.attempt.audio_stop.get_session_by_chat_id",
        return_value=session,
    ):
        with patch(
            "app.infra.websocket.attempt.audio_stop.get_internal_sio",
            return_value=mock_sio,
        ):
            with patch(
                "app.infra.websocket.attempt.audio_stop.get_pool",
                return_value=mock_pool,
            ):
                result = await attempt_audio_stop_internal_impl(
                    {"chat_id": "chat-stop", "sid": "caller-sid"}
                )

    assert result.chat_id == "chat-stop"
    assert result.stopped is True
    mock_sio.emit.assert_called_once()
    event_name = mock_sio.emit.call_args[0][0]
    assert event_name == "attempt.generate.audio.session_complete"


async def test_audio_stop_result_serialization():
    """AudioStopInternalResult serializes correctly."""
    result = AudioStopInternalResult(chat_id="c1", stopped=True)
    data = result.model_dump()

    assert data == {"chat_id": "c1", "stopped": True}
