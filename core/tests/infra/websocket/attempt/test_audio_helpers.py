"""Tests for audio_helpers — session lookup and cleanup re-exports."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.infra.websocket.attempt.audio_helpers import (
    cleanup_voice_session,
    get_session_for_group,
)
from app.infra.websocket.session_store import (
    AudioSession,
    create_session,
    remove_session,
)

pytestmark = pytest.mark.asyncio


def _make_session(group_id: str = "grp-1") -> AudioSession:
    """Create a minimal AudioSession for testing."""
    return AudioSession(
        sid="sid-1",
        chat_id="chat-1",
        run_id="run-1",
        group_id=group_id,
    )


async def test_get_session_for_group_returns_session():
    """get_session_for_group returns the session when it exists."""
    session = _make_session("grp-found")

    with patch(
        "app.infra.websocket.attempt.audio_helpers.get_session_by_group_id",
        return_value=session,
    ):
        result = get_session_for_group("grp-found")

    assert result is session
    assert result.group_id == "grp-found"


async def test_get_session_for_group_returns_none():
    """get_session_for_group returns None when no session exists."""
    with patch(
        "app.infra.websocket.attempt.audio_helpers.get_session_by_group_id",
        return_value=None,
    ):
        result = get_session_for_group("grp-missing")

    assert result is None


async def test_cleanup_voice_session_is_callable():
    """cleanup_voice_session is a re-export of cleanup_audio_session."""
    assert callable(cleanup_voice_session)


async def test_session_store_roundtrip():
    """create_session and get_session_for_group integrate correctly."""
    from app.infra.websocket import session_store

    # Use the real session store for this integration-level check
    session = session_store.create_session(
        sid="test-sid",
        chat_id="test-chat-1",
        run_id="test-run-1",
        group_id="test-grp-1",
    )

    try:
        found = session_store.get_session_by_group_id("test-grp-1")
        assert found is session
        assert found.chat_id == "test-chat-1"

        found_by_chat = session_store.get_session_by_chat_id("test-chat-1")
        assert found_by_chat is session
    finally:
        session_store.remove_session("test-chat-1")

    # After removal
    assert session_store.get_session_by_group_id("test-grp-1") is None
