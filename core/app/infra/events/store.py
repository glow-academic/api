"""Naive event store backed by calls_entry + persisted call receipts."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID, uuid4

from app.events.types import build_lifecycle_event_type
from app.infra.stream.registry import get_artifact_events_config
from app.infra.stream.types import EventEnvelope


def build_event_cursor(event: EventEnvelope) -> str:
    """Serialize an event cursor."""
    return f"{event.created_at.isoformat()}::{event.id}"


def build_operation_events(
    *,
    artifact: str,
    operation: str,
    entity_id: UUID | None,
    created_at: datetime,
    call_id: UUID | None,
    tool_id: UUID | None,
    arguments: dict,
    output: dict,
    group_id: UUID | None = None,
) -> list[EventEnvelope]:
    """Project operation input/output into lifecycle + domain events."""
    config = get_artifact_events_config(artifact)
    if config is None:
        return []

    operation_config = config.get_operation(operation)
    if operation_config is None:
        return []

    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            output = {"raw": output}

    success = not (isinstance(output, dict) and output.get("success") is False)
    events: list[EventEnvelope] = []
    domain_entity_ids: list[UUID]

    if operation_config.resolve_entity_ids is not None:
        try:
            domain_entity_ids = operation_config.resolve_entity_ids(
                arguments,
                output if isinstance(output, dict) else {},
            )
        except (TypeError, ValueError):
            domain_entity_ids = []
    elif entity_id is not None:
        domain_entity_ids = [entity_id]
    else:
        domain_entity_ids = []

    lifecycle_entity_id = entity_id
    if lifecycle_entity_id is None and len(domain_entity_ids) == 1:
        lifecycle_entity_id = domain_entity_ids[0]

    if operation_config.include_call_lifecycle:
        event_root = str(call_id or uuid4())
        started_event_type = build_lifecycle_event_type(artifact, operation, "started")
        events.append(
            EventEnvelope(
                id=f"{event_root}:{started_event_type}",
                event_type=started_event_type,
                artifact=artifact,
                operation=operation,
                created_at=created_at,
                group_id=group_id,
                entity_id=lifecycle_entity_id,
                call_id=call_id,
                tool_id=tool_id,
                payload={"arguments": arguments},
            )
        )
        lifecycle_type = build_lifecycle_event_type(
            artifact,
            operation,
            "completed" if success else "failed",
        )
        events.append(
            EventEnvelope(
                id=f"{event_root}:{lifecycle_type}",
                event_type=lifecycle_type,
                artifact=artifact,
                operation=operation,
                created_at=created_at,
                group_id=group_id,
                entity_id=lifecycle_entity_id,
                call_id=call_id,
                tool_id=tool_id,
                payload={"output": output},
            )
        )

    if (
        success
        and operation_config.project_domain_from_audit
        and len(operation_config.domain_event_names) == 1
    ):
        for event_type in operation_config.domain_event_names:
            target_entity_ids = domain_entity_ids or [entity_id]
            for target_entity_id in target_entity_ids:
                event_root = str(call_id or uuid4())
                events.append(
                    EventEnvelope(
                        id=f"{event_root}:{event_type}:{target_entity_id or 'collection'}",
                        event_type=event_type,
                        artifact=artifact,
                        operation=operation,
                        created_at=created_at,
                        group_id=group_id,
                        entity_id=target_entity_id,
                        call_id=call_id,
                        tool_id=tool_id,
                        payload={
                            "arguments": arguments,
                            "output": output,
                        },
                    )
                )

    return events


def _project_call_receipt(
    *,
    artifact: str,
    operation: str,
    entity_id: UUID | None,
    created_at: datetime,
    call_id: UUID,
    tool_id: UUID | None,
    receipt: dict,
) -> list[EventEnvelope]:
    """Project a stored call receipt into lifecycle + domain events."""
    return build_operation_events(
        artifact=artifact,
        operation=operation,
        entity_id=entity_id,
        created_at=created_at,
        call_id=call_id,
        tool_id=tool_id,
        arguments=receipt.get("arguments") or {},
        output=receipt.get("output") or {},
    )
