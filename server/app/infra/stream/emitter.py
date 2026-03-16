"""Canonical live event emission for artifact operations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.events.types import build_lifecycle_event_type
from app.infra.events.store import build_operation_events
from app.infra.stream.hub import publish
from app.infra.stream.types import EventEnvelope


async def emit_artifact_operation_started(
    *,
    artifact: str,
    operation: str,
    arguments: dict,
    entity_id: UUID | None = None,
    call_id: UUID | None = None,
    tool_id: UUID | None = None,
    created_at: datetime | None = None,
) -> None:
    """Publish only the started lifecycle event for an operation."""
    event_created_at = created_at or datetime.now(UTC)
    event_type = build_lifecycle_event_type(artifact, operation, "started")
    event_root = str(call_id or f"{artifact}:{operation}:{event_created_at.isoformat()}")
    await publish(
        EventEnvelope(
            id=f"{event_root}:{event_type}",
            event_type=event_type,
            artifact=artifact,
            operation=operation,
            created_at=event_created_at,
            entity_id=entity_id,
            call_id=call_id,
            tool_id=tool_id,
            payload={"arguments": arguments},
        )
    )


async def emit_artifact_operation_finished(
    *,
    artifact: str,
    operation: str,
    arguments: dict,
    output: dict,
    entity_id: UUID | None = None,
    call_id: UUID | None = None,
    tool_id: UUID | None = None,
    created_at: datetime | None = None,
) -> None:
    """Publish completed/failed lifecycle plus projected domain events."""
    events = build_operation_events(
        artifact=artifact,
        operation=operation,
        entity_id=entity_id,
        created_at=created_at or datetime.now(UTC),
        call_id=call_id,
        tool_id=tool_id,
        arguments=arguments,
        output=output,
    )
    for event in events:
        if event.event_type == build_lifecycle_event_type(artifact, operation, "started"):
            continue
        await publish(event)


async def emit_artifact_operation_events(
    *,
    artifact: str,
    operation: str,
    arguments: dict,
    output: dict,
    entity_id: UUID | None = None,
    call_id: UUID | None = None,
    tool_id: UUID | None = None,
    created_at: datetime | None = None,
) -> None:
    """Project and publish lifecycle + domain events for an artifact operation."""
    await emit_artifact_operation_started(
        artifact=artifact,
        operation=operation,
        arguments=arguments,
        entity_id=entity_id,
        call_id=call_id,
        tool_id=tool_id,
        created_at=created_at,
    )
    await emit_artifact_operation_finished(
        artifact=artifact,
        operation=operation,
        arguments=arguments,
        output=output,
        entity_id=entity_id,
        call_id=call_id,
        tool_id=tool_id,
        created_at=created_at,
    )


async def emit_artifact_operation_failure(
    *,
    artifact: str,
    operation: str,
    arguments: dict,
    message: str,
    error_type: str | None = None,
    entity_id: UUID | None = None,
    tool_id: UUID | None = None,
    created_at: datetime | None = None,
) -> None:
    """Publish failed lifecycle events for a failed operation."""
    output = {
        "success": False,
        "message": message,
        "error_type": error_type,
        "artifact": artifact,
        "operation": operation,
    }
    await emit_artifact_operation_finished(
        artifact=artifact,
        operation=operation,
        arguments=arguments,
        output=output,
        entity_id=entity_id,
        call_id=None,
        tool_id=tool_id,
        created_at=created_at,
    )
