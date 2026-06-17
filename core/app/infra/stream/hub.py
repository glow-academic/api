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

from app.infra.stream.types import EventEnvelope, is_non_droppable

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
        _put_sheddable(subscription.queue, event, subscription.group_id)


def _put_sheddable(
    queue: asyncio.Queue[EventEnvelope], event: EventEnvelope, group_id: UUID
) -> None:
    """Enqueue ``event``, evicting to stay bounded WITHOUT ever dropping a
    buffered NON-DROPPABLE frame.

    Fast path: a plain ``put_nowait`` on a non-full queue. On a full queue (a
    slow consumer), make room by dropping the OLDEST DROPPABLE frame — never a
    buffered terminal (``.completed`` / ``.failed``) or ``agent_completed``.
    The prior logic shed the *oldest* frame blindly to make room, which could
    evict an unread buffered terminal — dropping a terminal leaves a run-scoped
    watcher (``glow … watch <run_id>``) looping on keep-alives with no EOF, so
    it hangs forever (report-19 HUB1 / S4). Here a buffered terminal is kept and
    a droppable frame is shed instead.

    If EVERY buffered frame AND the incoming one are non-droppable (a queue
    entirely of load-bearing frames — pathological at depth 1000), we drop the
    oldest to stay bounded and log it, since we cannot grow without bound.

    All ops are non-blocking (`*_nowait`) and synchronous — no ``await`` — so
    the drain + refill is atomic w.r.t. the event loop; no producer or consumer
    can interleave mid-rebuild.
    """
    try:
        queue.put_nowait(event)
        return
    except asyncio.QueueFull:
        pass

    # Full: drain to a FIFO list (oldest → newest), append the newcomer, then
    # drop exactly one victim so the survivors fit (== _QUEUE_MAXSIZE).
    buffered: list[EventEnvelope] = []
    while True:
        try:
            buffered.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            break
    combined = buffered + [event]

    drop_idx = next(
        (i for i, e in enumerate(combined) if not is_non_droppable(e.event_type)),
        None,
    )
    if drop_idx is None:
        dropped = combined.pop(0)
        logger.error(
            "SSE queue full of non-droppable frames for group %s; forced to drop "
            "oldest terminal %s — watcher may hang",
            group_id,
            dropped.event_type,
        )
    else:
        combined.pop(drop_idx)

    for e in combined:
        try:
            queue.put_nowait(e)
        except asyncio.QueueFull:  # pragma: no cover — we removed exactly one
            logger.error(
                "SSE re-enqueue overflow for group %s; dropping %s",
                group_id,
                e.event_type,
            )
            break
