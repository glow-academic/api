"""In-process live event hub for SSE delivery.

Routes events by group_id. Subscribers join groups and receive
all events published to those groups.

- subscribe(group_id) → queue
- unsubscribe(queue)
- publish(event) → routes to subscribers whose group_id matches
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from app.infra.stream.types import EventEnvelope, is_run_terminal

logger = logging.getLogger(__name__)

# Cap each subscriber's buffer. A slow/throttled SSE consumer on a long-lived
# group-wide stream (run_id=None) would otherwise accumulate events without
# bound. With a cap, publish() sheds the oldest event for a full queue rather
# than growing memory or blocking the fan-out to the other subscribers.
_QUEUE_MAXSIZE: Final[int] = 1000


@dataclass(slots=True)
class _Subscription:
    queue: asyncio.Queue[EventEnvelope]
    group_id: UUID


_SUBSCRIPTIONS: Final[list[_Subscription]] = []


def subscribe(*, group_id: UUID) -> asyncio.Queue[EventEnvelope]:
    """Create a queue subscription for a specific group's events."""
    queue: asyncio.Queue[EventEnvelope] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
    _SUBSCRIPTIONS.append(_Subscription(queue=queue, group_id=group_id))
    return queue


def unsubscribe(queue: asyncio.Queue[EventEnvelope]) -> None:
    """Remove a queue subscription."""
    _SUBSCRIPTIONS[:] = [sub for sub in _SUBSCRIPTIONS if sub.queue is not queue]


async def publish(event: EventEnvelope) -> None:
    """Publish a live event to subscribers watching its group_id.

    Never blocks on a single subscriber: one slow consumer must not stall the
    fan-out to the others. When a subscriber's bounded queue is full we drop
    its OLDEST buffered event to make room for the new one, so memory stays
    bounded while the consumer keeps receiving the freshest events.
    """
    if not event.group_id:
        return
    for subscription in list(_SUBSCRIPTIONS):
        if event.group_id != subscription.group_id:
            continue
        queue = subscription.queue
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            # Slow consumer: shed the oldest event, then enqueue the newest.
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Lost a race with another producer that refilled the freed slot
                # before our put. For an ordinary mid-run frame this is fine —
                # drop it and keep the fan-out non-blocking. But a run TERMINAL
                # frame (``.completed`` / ``.failed`` / ``agent_completed`` …)
                # is load-bearing: dropping it leaves a run-scoped watcher
                # (``glow … watch <run_id>``) looping on keep-alives with no
                # EOF — it hangs forever (S4). Terminal frames are rare (one per
                # run) and must not be lost, so for them keep shedding the oldest
                # and retrying until the put lands (bounded by the queue depth so
                # this can never spin). Non-terminal frames keep the original
                # best-effort drop.
                if is_run_terminal(event.event_type):
                    delivered = False
                    for _ in range(_QUEUE_MAXSIZE + 1):
                        try:
                            queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        try:
                            queue.put_nowait(event)
                            delivered = True
                            break
                        except asyncio.QueueFull:
                            continue
                    if not delivered:
                        logger.error(
                            "SSE terminal frame %s undeliverable for group %s "
                            "after draining queue; watcher may hang",
                            event.event_type,
                            subscription.group_id,
                        )
                else:
                    # Lost a race with another producer refilling the slot; the
                    # event is dropped rather than blocking the fan-out.
                    logger.warning(
                        "SSE subscriber queue full for group %s; dropping event %s",
                        subscription.group_id,
                        event.event_type,
                    )
