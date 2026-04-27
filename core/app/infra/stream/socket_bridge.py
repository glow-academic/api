"""Bridge selected workflow socket events into live SSE artifact events."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.infra.stream.hub import publish
from app.infra.stream.types import EventEnvelope
from app.infra.websocket.socket_event import EmitFn, SocketEvent

_SOCKET_EVENT_TO_PUBLIC: dict[tuple[str, str], dict[str, str]] = {
    ("attempt", "start"): {
        "attempt.start.completed": "attempt.started",
    },
    ("attempt", "message"): {
        "attempt.message.assistant.progress": "attempt.chat.assistant.progress",
    },
    ("attempt", "grade"): {
        "attempt.chat_grade.progress": "attempt.chat.grade.progress",
    },
    ("attempt", "end"): {
        "attempt.complete.completed": "attempt.ended",
    },
    ("attempt", "stop"): {
        "attempt.stop.completed": "attempt.chat.stopped",
    },
    ("test", "start"): {
        "test.start.completed": "test.started",
        "test.run.invocation_started": "test.invocation.started",
    },
    ("test", "run"): {
        "test.run.started": "test.run.replay_started",
        "test.grade.started": "test.run.progress",
        "test.grade.progress": "test.run.progress",
        "test.run.completed": "test.run.replay_completed",
    },
    ("test", "invocation_complete"): {
        "test.end.completed": "test.invocation.completed",
    },
    ("test", "complete"): {
        "test_all_complete": "test.completed",
    },
    ("test", "stop"): {
        "test.stop.completed": "test.invocation.stopped",
    },
}


def wrap_emit_with_stream_bridge(
    *,
    artifact: str,
    operation: str,
    emit: EmitFn,
    group_id: UUID | None = None,
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
            # Prefer the explicit group_id; otherwise fish one out of event.data
            # since attempt/test workflow events carry it in payload.
            target_group_id = group_id
            if target_group_id is None and isinstance(event.data, dict):
                raw_gid = event.data.get("group_id")
                if isinstance(raw_gid, str):
                    try:
                        target_group_id = UUID(raw_gid)
                    except ValueError:
                        target_group_id = None
                elif isinstance(raw_gid, UUID):
                    target_group_id = raw_gid
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
                    group_id=target_group_id,
                    entity_id=target_entity_id,
                    payload=event.data,
                )
            )

    return _emit
