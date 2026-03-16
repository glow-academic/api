"""Shared event declaration types for centralized delivery."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

import asyncpg
from pydantic import BaseModel
from redis.asyncio import Redis

EventScope = Literal["entity", "collection"]
EventRecord = dict[str, Any]
EventPayload = dict[str, Any]
LifecyclePhase = Literal["started", "completed", "failed"]

CanSubscribe = Callable[..., Awaitable[bool]]
FilterEvents = Callable[[UUID, list[EventRecord]], Awaitable[list[EventRecord]]]
ResolveEntityIds = Callable[[EventPayload, EventPayload], list[UUID]]

# Type alias for model references in event configs.
EventModel = type[BaseModel]


# ---------------------------------------------------------------------------
# Shared error model for all failed lifecycle events
# ---------------------------------------------------------------------------


class OperationErrorEvent(BaseModel):
    """Payload for lifecycle ``failed`` events across all artifacts."""

    message: str
    error_type: str | None = None
    artifact: str | None = None
    operation: str | None = None


def build_lifecycle_event_type(
    artifact: str,
    operation: str,
    phase: LifecyclePhase,
) -> str:
    """Build the canonical public lifecycle event name."""
    return f"artifacts.{artifact}.{operation}.{phase}"


def build_default_lifecycle_event_types(
    artifact: str,
    operation: str,
) -> tuple[str, str, str]:
    """Build the canonical lifecycle event names for an operation."""
    return (
        build_lifecycle_event_type(artifact, operation, "started"),
        build_lifecycle_event_type(artifact, operation, "completed"),
        build_lifecycle_event_type(artifact, operation, "failed"),
    )


@dataclass(frozen=True)
class OperationEventConfig:
    """Declarative event policy for a single artifact operation.

    Two distinct dicts carry typed payload models:

    ``lifecycle_models``
        Keyed by phase (``started`` / ``completed`` / ``failed``).
        Deterministic — every operation boundary emits exactly these three.
        *started* → the request/input model.
        *completed* → the response/output model.
        *failed* → error model (typically ``OperationErrorEvent``).

    ``domain_events``
        Keyed by full event name (e.g. ``artifacts.attempt.assistant.progress``).
        These fire *during* the operation and can be any number with any shape.
    """

    operation: str
    scope: EventScope
    entity_key: str | None
    can_subscribe: CanSubscribe

    # Lifecycle payload types: phase → model
    lifecycle_models: dict[LifecyclePhase, EventModel | None] = field(
        default_factory=dict,
    )

    # Domain event payload types: event_name → model
    domain_events: dict[str, EventModel | None] = field(
        default_factory=dict,
    )

    filter_events: FilterEvents | None = None
    include_call_lifecycle: bool = True
    resolve_entity_ids: ResolveEntityIds | None = None
    project_domain_from_audit: bool = True

    @property
    def domain_event_names(self) -> tuple[str, ...]:
        """Return the domain event names (keys) as a tuple."""
        return tuple(self.domain_events.keys())


@dataclass(frozen=True)
class ArtifactEventsConfig:
    """Declarative event policy bundle for an artifact."""

    artifact: str
    operations: dict[str, OperationEventConfig]

    @property
    def event_types(self) -> tuple[str, ...]:
        """Flatten domain and lifecycle event types for the artifact."""
        return tuple(
            dict.fromkeys(
                event_type
                for operation in self.operations.values()
                for event_type in (
                    *operation.domain_event_names,
                    *(
                        build_default_lifecycle_event_types(
                            self.artifact,
                            operation.operation,
                        )
                        if operation.include_call_lifecycle
                        else ()
                    ),
                )
            )
        )

    def get_operation(self, operation: str) -> OperationEventConfig | None:
        """Resolve a single operation config."""
        return self.operations.get(operation)


async def default_filter_events(
    profile_id: UUID,
    events: list[EventRecord],
) -> list[EventRecord]:
    """Default no-op filter for artifacts without redaction rules yet."""
    del profile_id
    return events


async def require_authenticated_profile(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    session_id: UUID | None = None,
    event_types: list[str] | None = None,
) -> bool:
    """Placeholder auth check for artifacts that only need a resolved profile."""
    from app.infra.profile_identity_context import resolve_profile_identity_context

    del entity_id, event_types
    profile = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
    )
    return profile is not None
