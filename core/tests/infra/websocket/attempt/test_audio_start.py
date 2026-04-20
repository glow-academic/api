"""Tests for audio_start — internal impl for attempt audio start."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.infra.websocket.attempt.audio_start import AudioStartInternalResult

pytestmark = pytest.mark.asyncio


async def test_audio_start_result_model_fields():
    """AudioStartInternalResult carries expected fields."""
    result = AudioStartInternalResult(
        chat_id="chat-1",
        attempt_id="attempt-1",
        conversation_id="conv-1",
        group_id="group-1",
    )

    assert result.chat_id == "chat-1"
    assert result.attempt_id == "attempt-1"
    assert result.conversation_id == "conv-1"
    assert result.group_id == "group-1"


async def test_audio_start_result_serialization():
    """AudioStartInternalResult serializes to dict correctly."""
    result = AudioStartInternalResult(
        chat_id="c1",
        attempt_id="a1",
        conversation_id="v1",
        group_id="g1",
    )
    data = result.model_dump()

    assert data["chat_id"] == "c1"
    assert data["attempt_id"] == "a1"
    assert data["conversation_id"] == "v1"
    assert data["group_id"] == "g1"


async def test_audio_start_internal_impl_raises_without_profile(monkeypatch):
    """attempt_audio_start_internal_impl raises ValueError without profile_id."""
    from app.infra.websocket.attempt.audio_start import (
        attempt_audio_start_internal_impl,
    )

    with pytest.raises(ValueError, match="Missing profile_id"):
        await attempt_audio_start_internal_impl(
            {"chat_id": str(uuid4()), "session_id": str(uuid4())}
        )


async def test_audio_start_internal_impl_raises_without_session(monkeypatch):
    """attempt_audio_start_internal_impl raises ValueError without session_id."""
    from app.infra.websocket.attempt.audio_start import (
        attempt_audio_start_internal_impl,
    )

    with pytest.raises(ValueError, match="Missing session_id"):
        await attempt_audio_start_internal_impl(
            {"chat_id": str(uuid4()), "profile_id": str(uuid4())}
        )
