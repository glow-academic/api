"""In-process live event hub for SSE delivery.

This is intentionally simple:
- one process
- in-memory subscriber queues
- no durability

Durability/replay still comes from the persisted audit/call history.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from app.infra.stream.types import EventEnvelope


@dataclass(slots=True)
class _Subscription:
    queue: asyncio.Queue[EventEnvelope]
    artifact: str
    operation: str | None
    entity_id: UUID | None
    event_types: set[str] | None


_SUBSCRIPTIONS: Final[list[_Subscription]] = []


def subscribe(
    *,
    artifact: str,
    operation: str | None = None,
    entity_id: UUID | None = None,
    event_types: list[str] | None = None,
) -> asyncio.Queue[EventEnvelope]:
    """Create a queue subscription for live artifact events.

    When ``operation`` is ``None`` or ``"*"``, the subscription matches
    all operations for the given artifact.
    """
    resolved_operation = None if operation == "*" else operation
    queue: asyncio.Queue[EventEnvelope] = asyncio.Queue()
    _SUBSCRIPTIONS.append(
        _Subscription(
            queue=queue,
            artifact=artifact,
            operation=resolved_operation,
            entity_id=entity_id,
            event_types=set(event_types) if event_types else None,
        )
    )
    return queue


def unsubscribe(queue: asyncio.Queue[EventEnvelope]) -> None:
    """Remove a queue subscription."""
    _SUBSCRIPTIONS[:] = [sub for sub in _SUBSCRIPTIONS if sub.queue is not queue]


async def publish(event: EventEnvelope) -> None:
    """Publish a live event to matching subscribers."""
    for subscription in list(_SUBSCRIPTIONS):
        if event.artifact != subscription.artifact:
            continue
        if (
            subscription.operation is not None
            and event.operation != subscription.operation
        ):
            continue
        if (
            subscription.entity_id is not None
            and event.entity_id != subscription.entity_id
        ):
            continue
        if (
            subscription.event_types is not None
            and event.event_type not in subscription.event_types
        ):
            continue
        await subscription.queue.put(event)
