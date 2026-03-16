"""Tests for generation_events_impl — EmitFn pattern.

All handlers are pure pass-throughs: data in → SocketEvent out.
Uses recording_emit() to capture events — no mocks needed.
"""

from __future__ import annotations

import pytest

from app.infra.websocket.generation_events_impl import (
    call_complete_impl,
    generation_error_impl,
    image_complete_impl,
    image_start_impl,
    text_progress_impl,
    video_complete_impl,
    video_progress_impl,
    video_start_impl,
)
from app.infra.websocket.socket_event import recording_emit

# ═══════════════════════════════════════════════════════════════════════════
# generation_error
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestGenerationError:
    async def test_no_sid_emits_nothing(self):
        emit, events = recording_emit()
        await generation_error_impl({"sid": ""}, emit=emit)
        assert events == []

    async def test_emits_error_to_generation_channel(self):
        emit, events = recording_emit()
        await generation_error_impl(
            {
                "sid": "s1",
                "artifact_type": "agent",
                "error_message": "boom",
                "run_id": "r1",
            },
            emit=emit,
        )
        assert len(events) == 1
        e = events[0]
        assert e.event == "generation_channel"
        assert e.data["type"] == "error"
        assert e.data["message"] == "boom"
        assert e.data["artifact_type"] == "agent"

    async def test_falls_back_to_message_field(self):
        emit, events = recording_emit()
        await generation_error_impl({"sid": "s1", "message": "fallback msg"}, emit=emit)
        assert events[0].data["message"] == "fallback msg"

    async def test_default_error_message(self):
        emit, events = recording_emit()
        await generation_error_impl({"sid": "s1"}, emit=emit)
        assert events[0].data["message"] == "An error occurred during generation"


# ═══════════════════════════════════════════════════════════════════════════
# text_progress
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestTextProgress:
    async def test_non_attempt_artifact_skipped(self):
        emit, events = recording_emit()
        await text_progress_impl({"artifact_type": "agent"}, emit=emit)
        assert events == []

    async def test_grade_skipped(self):
        emit, events = recording_emit()
        await text_progress_impl(
            {"artifact_type": "chat", "metadata": {"grade_id": "g1"}},
            emit=emit,
        )
        assert events == []

    async def test_emits_assistant_progress(self):
        emit, events = recording_emit()
        await text_progress_impl(
            {
                "artifact_type": "chat",
                "sid": "s1",
                "delta": "hello",
                "metadata": {"chat_id": "c1"},
            },
            emit=emit,
        )
        assert len(events) == 1
        assert events[0].event == "attempt_assistant_progress"
        assert events[0].data["content"] == "hello"
        assert events[0].data["chat_id"] == "c1"


# ═══════════════════════════════════════════════════════════════════════════
# call_complete
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestCallComplete:
    async def test_non_tool_result_skipped(self):
        emit, events = recording_emit()
        await call_complete_impl({"event_type": "other"}, emit=emit)
        assert events == []

    async def test_non_attempt_skipped(self):
        emit, events = recording_emit()
        await call_complete_impl(
            {"event_type": "tool_result", "artifact_type": "agent"}, emit=emit
        )
        assert events == []

    async def test_hints_emitted(self):
        emit, events = recording_emit()
        await call_complete_impl(
            {
                "event_type": "tool_result",
                "artifact_type": "chat",
                "sid": "s1",
                "entry_type": "hints",
                "result": {"hints": [{"text": "try this"}]},
                "metadata": {"chat_id": "c1"},
            },
            emit=emit,
        )
        assert len(events) == 1
        assert events[0].event == "attempt_assistant_hints"
        assert events[0].data["hints"] == [{"text": "try this"}]

    async def test_grade_progress_emitted(self):
        emit, events = recording_emit()
        await call_complete_impl(
            {
                "event_type": "tool_result",
                "artifact_type": "attempt",
                "sid": "s1",
                "result": {"score": 5},
                "metadata": {"chat_id": "c1", "grade_id": "g1"},
            },
            emit=emit,
        )
        assert len(events) == 1
        assert events[0].event == "attempt_grade_progress"
        assert events[0].data["grade_id"] == "g1"

    async def test_hints_and_grade_both_emitted(self):
        emit, events = recording_emit()
        await call_complete_impl(
            {
                "event_type": "tool_result",
                "artifact_type": "chat",
                "sid": "s1",
                "entry_type": "hints",
                "result": {"hints": []},
                "metadata": {"chat_id": "c1", "grade_id": "g1"},
            },
            emit=emit,
        )
        assert len(events) == 2
        assert events[0].event == "attempt_assistant_hints"
        assert events[1].event == "attempt_grade_progress"


# ═══════════════════════════════════════════════════════════════════════════
# Media events
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestMediaEvents:
    async def test_image_start_no_sid(self):
        emit, events = recording_emit()
        await image_start_impl({"sid": ""}, emit=emit)
        assert events == []

    async def test_image_start(self):
        emit, events = recording_emit()
        await image_start_impl(
            {"sid": "s1", "artifact_type": "agent", "run_id": "r1"},
            emit=emit,
        )
        assert len(events) == 1
        assert events[0].data["type"] == "media_progress"
        assert events[0].data["modality"] == "image"
        assert events[0].data["status"] == "started"

    async def test_image_complete(self):
        emit, events = recording_emit()
        await image_complete_impl(
            {"sid": "s1", "file_path": "/img.png", "upload_id": "u1"},
            emit=emit,
        )
        assert events[0].data["type"] == "media_complete"
        assert events[0].data["modality"] == "image"
        assert events[0].data["file_path"] == "/img.png"

    async def test_video_start(self):
        emit, events = recording_emit()
        await video_start_impl({"sid": "s1"}, emit=emit)
        assert events[0].data["modality"] == "video"
        assert events[0].data["status"] == "started"

    async def test_video_progress(self):
        emit, events = recording_emit()
        await video_progress_impl({"sid": "s1", "message": "50% done"}, emit=emit)
        assert events[0].data["status"] == "in_progress"
        assert events[0].data["message"] == "50% done"

    async def test_video_complete(self):
        emit, events = recording_emit()
        await video_complete_impl(
            {"sid": "s1", "file_path": "/vid.mp4", "mime_type": "video/mp4"},
            emit=emit,
        )
        assert events[0].data["type"] == "media_complete"
        assert events[0].data["modality"] == "video"
        assert events[0].data["file_path"] == "/vid.mp4"
