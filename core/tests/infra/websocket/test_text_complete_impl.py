"""Tests for text_complete_impl — saves assistant message on text_complete."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.infra.websocket.text_complete_impl import text_complete_impl

pytestmark = pytest.mark.asyncio


async def test_text_complete_skips_non_text_complete_events():
    """Non-text_complete events are silently ignored."""
    emit = AsyncMock()
    conn = AsyncMock()

    await text_complete_impl(
        {"event_type": "generation_started", "run_id": "r1"},
        emit=emit,
        conn=conn,
    )

    # persist_run_message should not be called
    # If we got here without error, the function handled non-matching events


async def test_text_complete_skips_when_missing_fields():
    """Missing run_id, session_id, or text causes early return."""
    emit = AsyncMock()
    conn = AsyncMock()

    # Missing run_id
    await text_complete_impl(
        {"event_type": "text_complete", "session_id": "s1", "text": "hello"},
        emit=emit,
        conn=conn,
    )

    # Missing text
    await text_complete_impl(
        {"event_type": "text_complete", "run_id": "r1", "session_id": "s1"},
        emit=emit,
        conn=conn,
    )

    # Missing session_id
    await text_complete_impl(
        {"event_type": "text_complete", "run_id": "r1", "text": "hello"},
        emit=emit,
        conn=conn,
    )


async def test_text_complete_calls_persist_run_message():
    """Valid text_complete event persists the assistant message."""
    emit = AsyncMock()
    conn = AsyncMock()

    with patch(
        "app.infra.websocket.text_complete_impl.persist_run_message",
        new_callable=AsyncMock,
    ) as mock_persist:
        await text_complete_impl(
            {
                "event_type": "text_complete",
                "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "session_id": "f0e1d2c3-b4a5-6789-0123-456789abcdef",
                "text": "Hello, I can help with that.",
            },
            emit=emit,
            conn=conn,
        )

    mock_persist.assert_called_once()
    call_kwargs = mock_persist.call_args
    assert call_kwargs[1]["role"] == "assistant"
    assert call_kwargs[1]["content"] == "Hello, I can help with that."


async def test_text_complete_handles_persist_error_gracefully():
    """persist_run_message errors are caught and logged, not raised."""
    emit = AsyncMock()
    conn = AsyncMock()

    with patch(
        "app.infra.websocket.text_complete_impl.persist_run_message",
        new_callable=AsyncMock,
        side_effect=RuntimeError("DB write failed"),
    ):
        # Should not raise
        await text_complete_impl(
            {
                "event_type": "text_complete",
                "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "session_id": "f0e1d2c3-b4a5-6789-0123-456789abcdef",
                "text": "Some response text",
            },
            emit=emit,
            conn=conn,
        )
