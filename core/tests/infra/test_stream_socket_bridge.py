from __future__ import annotations

from uuid import UUID

import pytest

from app.infra.stream.hub import subscribe, unsubscribe
from app.infra.stream.socket_bridge import wrap_emit_with_stream_bridge
from app.infra.websocket.socket_event import internal_event, recording_emit


@pytest.mark.asyncio
async def test_wrap_emit_with_stream_bridge_publishes_attempt_message_event() -> None:
    emit, recorded = recording_emit()
    bridged = wrap_emit_with_stream_bridge(
        artifact="attempt",
        operation="message",
        emit=emit,
        entity_id=UUID("11111111-1111-1111-1111-111111111111"),
    )
    queue = subscribe(
        artifact="attempt",
        operation="message",
        entity_id=UUID("11111111-1111-1111-1111-111111111111"),
    )
    try:
        await bridged(
            [
                internal_event(
                    "attempt_assistant_complete",
                    {
                        "chat_id": "11111111-1111-1111-1111-111111111111",
                        "content": "done",
                    },
                )
            ]
        )

        assert [event.event for event in recorded] == ["attempt_assistant_complete"]
        published = await queue.get()
        assert published.event_type == "artifacts.attempt.assistant.complete"
        assert published.entity_id == UUID("11111111-1111-1111-1111-111111111111")
        assert published.payload["content"] == "done"
    finally:
        unsubscribe(queue)


@pytest.mark.asyncio
async def test_wrap_emit_with_stream_bridge_publishes_test_run_progress_event() -> None:
    emit, recorded = recording_emit()
    bridged = wrap_emit_with_stream_bridge(
        artifact="test",
        operation="run",
        emit=emit,
        entity_id=UUID("22222222-2222-2222-2222-222222222222"),
    )
    queue = subscribe(
        artifact="test",
        operation="run",
        entity_id=UUID("22222222-2222-2222-2222-222222222222"),
    )
    try:
        await bridged(
            [
                internal_event(
                    "test_grade_progress",
                    {
                        "invocation_id": "22222222-2222-2222-2222-222222222222",
                        "score": 0.9,
                    },
                )
            ]
        )

        assert [event.event for event in recorded] == ["test_grade_progress"]
        published = await queue.get()
        assert published.event_type == "artifacts.test.run.progress"
        assert published.entity_id == UUID("22222222-2222-2222-2222-222222222222")
        assert published.payload["score"] == 0.9
    finally:
        unsubscribe(queue)


@pytest.mark.asyncio
async def test_wrap_emit_with_stream_bridge_uses_distinct_test_run_domain_names() -> None:
    emit, recorded = recording_emit()
    bridged = wrap_emit_with_stream_bridge(
        artifact="test",
        operation="run",
        emit=emit,
        entity_id=UUID("66666666-6666-6666-6666-666666666666"),
    )
    queue = subscribe(
        artifact="test",
        operation="run",
        entity_id=UUID("66666666-6666-6666-6666-666666666666"),
    )
    try:
        await bridged(
            [
                internal_event(
                    "test_run_started",
                    {
                        "invocation_id": "66666666-6666-6666-6666-666666666666",
                        "run_id": "77777777-7777-7777-7777-777777777777",
                    },
                ),
                internal_event(
                    "test_run_complete",
                    {
                        "invocation_id": "66666666-6666-6666-6666-666666666666",
                        "run_id": "77777777-7777-7777-7777-777777777777",
                    },
                ),
            ]
        )

        assert [event.event for event in recorded] == [
            "test_run_started",
            "test_run_complete",
        ]
        first = await queue.get()
        second = await queue.get()
        assert first.event_type == "artifacts.test.run.replay_started"
        assert second.event_type == "artifacts.test.run.replay_completed"
    finally:
        unsubscribe(queue)


@pytest.mark.asyncio
async def test_wrap_emit_with_stream_bridge_skips_attempt_server_owned_domain_events() -> None:
    emit, recorded = recording_emit()
    bridged = wrap_emit_with_stream_bridge(
        artifact="attempt",
        operation="grade",
        emit=emit,
        entity_id=UUID("33333333-3333-3333-3333-333333333333"),
    )
    queue = subscribe(
        artifact="attempt",
        operation="grade",
        entity_id=UUID("33333333-3333-3333-3333-333333333333"),
    )
    try:
        await bridged(
            [
                internal_event(
                    "attempt_grade_complete",
                    {
                        "chat_id": "44444444-4444-4444-4444-444444444444",
                        "grade_id": "55555555-5555-5555-5555-555555555555",
                    },
                )
            ]
        )

        assert [event.event for event in recorded] == ["attempt_grade_complete"]
        assert queue.empty()
    finally:
        unsubscribe(queue)
