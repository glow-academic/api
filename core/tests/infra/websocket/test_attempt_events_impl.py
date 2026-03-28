"""Tests for attempt_events_impl — compatibility re-export module."""

from __future__ import annotations

import inspect

import pytest

from app.infra.websocket.attempt_events_impl import (
    attempt_message_impl,
    attempt_next_impl,
    attempt_proceed_impl,
    attempt_start_impl,
    audio_delta_impl,
    audio_error_impl,
    audio_response_cancelled_impl,
    audio_session_start_impl,
    audio_speech_delta_impl,
    audio_speech_start_impl,
    audio_stop_impl,
    emit_chat_generate_impl,
    speech_complete_impl,
    user_complete_impl,
    user_progress_impl,
    user_start_impl,
)

pytestmark = pytest.mark.asyncio


async def test_re_exports_are_async_callables():
    """All re-exported attempt workflow functions are async callables."""
    for fn in [
        attempt_start_impl,
        attempt_next_impl,
        attempt_proceed_impl,
        attempt_message_impl,
        emit_chat_generate_impl,
        audio_session_start_impl,
        audio_stop_impl,
        audio_delta_impl,
        audio_speech_start_impl,
        audio_speech_delta_impl,
        speech_complete_impl,
        audio_error_impl,
        audio_response_cancelled_impl,
        user_start_impl,
        user_progress_impl,
        user_complete_impl,
    ]:
        assert inspect.iscoroutinefunction(fn), f"{fn.__name__} should be async"


async def test_attempt_start_impl_exists_and_is_callable():
    """attempt_start_impl is the canonical workflow entry point."""
    assert callable(attempt_start_impl)
    assert inspect.iscoroutinefunction(attempt_start_impl)


async def test_audio_workflow_functions_are_async():
    """Audio workflow functions are async callables."""
    for fn in [
        audio_session_start_impl,
        audio_stop_impl,
        audio_delta_impl,
    ]:
        assert inspect.iscoroutinefunction(fn), f"{fn.__name__} should be async"
