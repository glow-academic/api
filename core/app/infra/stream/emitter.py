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
    group_id: UUID | None = None,
    entity_id: UUID | None = None,
    call_id: UUID | None = None,
    tool_id: UUID | None = None,
    created_at: datetime | None = None,
    role: str = "user",
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
            group_id=group_id,
            entity_id=entity_id,
            call_id=call_id,
            tool_id=tool_id,
            payload={"arguments": arguments, "role": role},
        )
    )


async def _publish_lifecycle(
    *,
    artifact: str,
    operation: str,
    phase: str,
    payload: dict,
    group_id: UUID | None,
    entity_id: UUID | None,
    call_id: UUID | None,
    tool_id: UUID | None,
    created_at: datetime,
) -> None:
    """Publish a single lifecycle envelope. Used by ``finished`` to emit
    completed/failed unconditionally — even for operations that don't
    register an ``OperationEventConfig``. Lifecycle is a property of
    "this op got audited," not of "this op opted into projections."
    """
    event_type = build_lifecycle_event_type(artifact, operation, phase)
    event_root = str(call_id or f"{artifact}:{operation}:{created_at.isoformat()}")
    await publish(
        EventEnvelope(
            id=f"{event_root}:{event_type}",
            event_type=event_type,
            artifact=artifact,
            operation=operation,
            created_at=created_at,
            group_id=group_id,
            entity_id=entity_id,
            call_id=call_id,
            tool_id=tool_id,
            payload=payload,
        )
    )


async def emit_artifact_operation_finished(
    *,
    artifact: str,
    operation: str,
    arguments: dict,
    output: dict,
    group_id: UUID | None = None,
    entity_id: UUID | None = None,
    call_id: UUID | None = None,
    tool_id: UUID | None = None,
    created_at: datetime | None = None,
    role: str = "user",
) -> None:
    """Publish completed/failed lifecycle plus any projected domain events.

    The lifecycle pair always fires (regardless of artifact-events config).
    Domain events are only projected when the operation has a config in
    ``app.events.{artifact}`` — those are additive on top.
    """
    event_created_at = created_at or datetime.now(UTC)
    success = not (isinstance(output, dict) and output.get("success") is False)
    phase = "completed" if success else "failed"

    # 1. Always emit the lifecycle envelope — the single source of truth
    #    for "the audited operation finished."
    await _publish_lifecycle(
        artifact=artifact,
        operation=operation,
        phase=phase,
        payload={"output": output, "role": role},
        group_id=group_id,
        entity_id=entity_id,
        call_id=call_id,
        tool_id=tool_id,
        created_at=event_created_at,
    )

    # 2. Optional projected domain events for operations that have an
    #    OperationEventConfig. ``build_operation_events`` may also emit
    #    its own lifecycle envelopes (started/completed/failed) when
    #    ``include_call_lifecycle`` is set — skip those to avoid the
    #    started having already fired and the completed/failed being a
    #    duplicate of step 1.
    started = build_lifecycle_event_type(artifact, operation, "started")
    completed = build_lifecycle_event_type(artifact, operation, "completed")
    failed = build_lifecycle_event_type(artifact, operation, "failed")
    skip_lifecycle = {started, completed, failed}

    events = build_operation_events(
        artifact=artifact,
        operation=operation,
        entity_id=entity_id,
        created_at=event_created_at,
        call_id=call_id,
        tool_id=tool_id,
        arguments=arguments,
        output=output,
        group_id=group_id,
    )
    for event in events:
        if event.event_type in skip_lifecycle:
            continue
        await publish(event)


async def emit_artifact_operation_events(
    *,
    artifact: str,
    operation: str,
    arguments: dict,
    output: dict,
    group_id: UUID | None = None,
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
        group_id=group_id,
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
        group_id=group_id,
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
    group_id: UUID | None = None,
    entity_id: UUID | None = None,
    call_id: UUID | None = None,
    tool_id: UUID | None = None,
    created_at: datetime | None = None,
    role: str = "user",
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
        group_id=group_id,
        entity_id=entity_id,
        call_id=call_id,
        tool_id=tool_id,
        created_at=created_at,
        role=role,
    )
