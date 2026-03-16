"""Bridge selected workflow socket events into live SSE artifact events."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.infra.stream.hub import publish
from app.infra.stream.types import EventEnvelope
from app.infra.websocket.socket_event import EmitFn, SocketEvent

_SOCKET_EVENT_TO_PUBLIC: dict[tuple[str, str], dict[str, str]] = {
    ("attempt", "start"): {
        "attempt_started": "artifacts.attempt.started",
    },
    ("attempt", "message"): {
        "attempt_assistant_start": "artifacts.attempt.assistant.start",
        "attempt_assistant_progress": "artifacts.attempt.assistant.progress",
        "attempt_assistant_complete": "artifacts.attempt.assistant.complete",
    },
    ("attempt", "grade"): {
        "attempt_grade_start": "artifacts.attempt.grade.start",
        "attempt_grade_progress": "artifacts.attempt.grade.progress",
    },
    ("attempt", "end"): {
        "attempt_ended": "artifacts.attempt.ended",
        "attempt_chat_ended": "artifacts.attempt.chat_ended",
    },
    ("attempt", "response"): {
        "attempt_response_result": "artifacts.attempt.response.saved",
    },
    ("attempt", "stop"): {
        "attempt_stopped": "artifacts.attempt.stopped",
    },
    ("test", "start"): {
        "test_started": "artifacts.test.started",
    },
    ("test", "run"): {
        "test_run_started": "artifacts.test.run.replay_started",
        "test_grade_start": "artifacts.test.run.progress",
        "test_grade_progress": "artifacts.test.run.progress",
        "test_run_complete": "artifacts.test.run.replay_completed",
    },
    ("test", "end"): {
        "test_ended": "artifacts.test.ended",
        "test_all_complete": "artifacts.test.ended",
    },
    ("test", "stop"): {
        "test_stopped": "artifacts.test.stopped",
    },
}


def wrap_emit_with_stream_bridge(
    *,
    artifact: str,
    operation: str,
    emit: EmitFn,
    entity_id: UUID | None = None,
    call_id: UUID | None = None,
) -> EmitFn:
    """Wrap an EmitFn so matching socket events are also published live.

    When call_id is provided, it is injected into every event's data dict
    so output handlers can append to the call receipt.
    """

    event_map = _SOCKET_EVENT_TO_PUBLIC.get((artifact, operation))
    if not event_map and not call_id:
        return emit

    async def _emit(events: list[SocketEvent]) -> None:
        # Inject call_id into event data if available
        if call_id:
            for event in events:
                if isinstance(event.data, dict):
                    event.data["call_id"] = str(call_id)

        await emit(events)

        if not event_map:
            return

        created_at = datetime.now(UTC)
        published: set[tuple[str, UUID | None, str]] = set()
        for event in events:
            public_event_type = event_map.get(event.event)
            if public_event_type is None:
                continue
            target_entity_id = entity_id
            dedupe_key = (
                public_event_type,
                target_entity_id,
                str(event.data),
            )
            if dedupe_key in published:
                continue
            published.add(dedupe_key)
            await publish(
                EventEnvelope(
                    id=f"{uuid4()}:{public_event_type}",
                    event_type=public_event_type,
                    artifact=artifact,
                    operation=operation,
                    created_at=created_at,
                    entity_id=target_entity_id,
                    payload=event.data,
                )
            )

    return _emit
