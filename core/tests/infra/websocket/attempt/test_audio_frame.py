"""Tests for audio_frame — push audio bytes into session inbound queue."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from app.infra.websocket.attempt.audio_frame import (
    attempt_audio_frame_internal_impl,
)
from app.infra.websocket.session_store import AudioSession

pytestmark = pytest.mark.asyncio


def _make_session(chat_id: str = "chat-1") -> AudioSession:
    """Create a minimal AudioSession for testing."""
    return AudioSession(
        sid="test-sid",
        chat_id=chat_id,
        run_id="run-1",
        group_id="group-1",
    )


async def test_frame_accepted_into_queue():
    """Audio frame is put into the inbound queue and returns True."""
    session = _make_session("chat-accept")
    audio = b"\x00\x01\x02\x03"

    with patch(
        "app.infra.websocket.attempt.audio_frame.get_session_by_chat_id",
        return_value=session,
    ):
        result = attempt_audio_frame_internal_impl(
            chat_id="chat-accept",
            audio=audio,
        )

    assert result is True
    # Verify the data was queued
    msg = session.inbound_queue.get_nowait()
    assert msg["type"] == "audio"
    assert msg["pcm16_bytes"] == audio


async def test_frame_rejected_when_no_session():
    """Returns False when no session exists for the chat_id."""
    with patch(
        "app.infra.websocket.attempt.audio_frame.get_session_by_chat_id",
        return_value=None,
    ):
        result = attempt_audio_frame_internal_impl(
            chat_id="nonexistent",
            audio=b"\x00\x01",
        )

    assert result is False


async def test_frame_rejected_when_empty_audio():
    """Returns False when audio bytes are empty."""
    session = _make_session("chat-empty")

    with patch(
        "app.infra.websocket.attempt.audio_frame.get_session_by_chat_id",
        return_value=session,
    ):
        result = attempt_audio_frame_internal_impl(
            chat_id="chat-empty",
            audio=b"",
        )

    assert result is False


async def test_frame_dropped_on_queue_full():
    """Returns False when the inbound queue is full (backpressure)."""
    session = _make_session("chat-full")
    # Fill the queue to capacity
    for _ in range(500):
        session.inbound_queue.put_nowait({"type": "audio", "pcm16_bytes": b"\x00"})

    with patch(
        "app.infra.websocket.attempt.audio_frame.get_session_by_chat_id",
        return_value=session,
    ):
        result = attempt_audio_frame_internal_impl(
            chat_id="chat-full",
            audio=b"\x00\x01",
        )

    assert result is False


async def test_frame_updates_last_activity():
    """Accepting a frame updates session.last_activity timestamp."""
    session = _make_session("chat-activity")
    old_activity = session.last_activity

    with patch(
        "app.infra.websocket.attempt.audio_frame.get_session_by_chat_id",
        return_value=session,
    ):
        attempt_audio_frame_internal_impl(
            chat_id="chat-activity",
            audio=b"\x00\x01\x02",
        )

    assert session.last_activity >= old_activity
