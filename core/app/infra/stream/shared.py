"""Shared subscription validation for event delivery transports."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException

from app.events.types import ArtifactEventsConfig, OperationEventConfig
from app.infra.globals import get_pool, get_redis_client
from app.infra.stream.registry import get_artifact_events_config


async def resolve_subscription(
    *,
    artifact: str,
    operation: str,
    entity_id: UUID | None,
    profile_id: UUID | None,
    session_id: UUID | None,
    event_types: list[str] | None = None,
) -> tuple[ArtifactEventsConfig, OperationEventConfig]:
    """Validate and resolve an event subscription.

    Shared across all four delivery transports (poll, SSE, WebSocket,
    webhooks).  Raises ``HTTPException`` on validation failure and returns
    the resolved artifact / operation configs on success.
    """
    config = get_artifact_events_config(artifact)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"No event registry found for artifact '{artifact}'.",
        )

    operation_config = config.get_operation(operation)
    if operation_config is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No event operation '{operation}' registered for "
                f"artifact '{artifact}'."
            ),
        )

    if operation_config.scope == "entity" and entity_id is None:
        raise HTTPException(
            status_code=400,
            detail=(f"entity_id is required for {artifact}.{operation} events."),
        )

    if event_types:
        invalid = [
            event_type
            for event_type in event_types
            if event_type not in config.event_types
        ]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported event types for {artifact}: " + ", ".join(invalid)
                ),
            )

    if not profile_id:
        raise HTTPException(
            status_code=401,
            detail="Profile ID is required. Please sign in again.",
        )

    allowed = await operation_config.can_subscribe(
        get_pool(),
        get_redis_client(),
        profile_id=profile_id,
        entity_id=entity_id,
        session_id=session_id,
        event_types=event_types,
    )
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=(f"You don't have access to {artifact}.{operation} events."),
        )

    return config, operation_config
