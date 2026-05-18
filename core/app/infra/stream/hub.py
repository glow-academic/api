"""In-process live event hub for SSE delivery.

Routes events by group_id. Subscribers join groups and receive
all events published to those groups.

- subscribe(group_id) → queue
- unsubscribe(queue)
- publish(event) → routes to subscribers whose group_id matches
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
    group_id: UUID


_SUBSCRIPTIONS: Final[list[_Subscription]] = []


def subscribe(*, group_id: UUID) -> asyncio.Queue[EventEnvelope]:
    """Create a queue subscription for a specific group's events."""
    queue: asyncio.Queue[EventEnvelope] = asyncio.Queue()
    _SUBSCRIPTIONS.append(_Subscription(queue=queue, group_id=group_id))
    return queue


def unsubscribe(queue: asyncio.Queue[EventEnvelope]) -> None:
    """Remove a queue subscription."""
    _SUBSCRIPTIONS[:] = [sub for sub in _SUBSCRIPTIONS if sub.queue is not queue]


async def publish(event: EventEnvelope) -> None:
    """Publish a live event to subscribers watching its group_id."""
    if not event.group_id:
        return
    for subscription in list(_SUBSCRIPTIONS):
        if event.group_id == subscription.group_id:
            await subscription.queue.put(event)
