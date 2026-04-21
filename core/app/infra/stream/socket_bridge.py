"""Bridge selected workflow socket events into live SSE artifact events."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.infra.stream.hub import publish
from app.infra.stream.types import EventEnvelope
from app.infra.websocket.socket_event import EmitFn, SocketEvent

_SOCKET_EVENT_TO_PUBLIC: dict[tuple[str, str], dict[str, str]] = {
    ("attempt", "start"): {
        "attempt.start.completed": "artifacts.attempt.started",
    },
    ("attempt", "message"): {
        "attempt.message.assistant.progress": "artifacts.attempt.chat.assistant.progress",
    },
    ("attempt", "grade"): {
        "attempt.chat_grade.progress": "artifacts.attempt.chat.grade.progress",
    },
    ("attempt", "end"): {
        "attempt.complete.completed": "artifacts.attempt.ended",
    },
    ("attempt", "stop"): {
        "attempt.stop.completed": "artifacts.attempt.chat.stopped",
    },
    ("test", "start"): {
        "test.start.completed": "artifacts.test.started",
    },
    ("test", "run"): {
        "test.run.started": "artifacts.test.run.replay_started",
        "test.grade.started": "artifacts.test.run.progress",
        "test.grade.progress": "artifacts.test.run.progress",
        "test.run.completed": "artifacts.test.run.replay_completed",
    },
    ("test", "end"): {
        "test.end.completed": "artifacts.test.ended",
        "test_all_complete": "artifacts.test.ended",
    },
    ("test", "stop"): {
        "test.stop.completed": "artifacts.test.stopped",
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
