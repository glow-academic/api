"""Bounded per-subscriber SSE queue in the live event hub.

A slow consumer on a long-lived group-wide stream must not grow memory
without bound. The subscriber queue is capped; publish() sheds the oldest
event when a queue is full, never blocks the fan-out to other subscribers,
and keeps disconnect/unsubscribe cleanup intact.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.infra.stream import hub
from app.infra.stream.hub import (
    _QUEUE_MAXSIZE,
    publish,
    subscribe,
    unsubscribe,
)
from app.infra.stream.types import EventEnvelope

pytestmark = pytest.mark.asyncio


def _event(group_id, *, seq: int, event_type: str = "simulation.generate.progress") -> EventEnvelope:
    return EventEnvelope(
        id=f"evt-{seq}",
        event_type=event_type,
        artifact="simulation",
        operation="generate",
        created_at=datetime.now(UTC),
        group_id=group_id,
        payload={"seq": seq},
    )


@pytest.fixture(autouse=True)
def _clear_subscriptions():
    """Isolate the module-global subscription list per test."""
    hub._SUBSCRIPTIONS.clear()
    yield
    hub._SUBSCRIPTIONS.clear()


async def test_subscribe_creates_bounded_queue():
    group_id = uuid4()
    queue = subscribe(group_id=group_id)
    try:
        assert queue.maxsize == _QUEUE_MAXSIZE
        assert queue.maxsize > 0
    finally:
        unsubscribe(queue)


async def test_publish_drops_oldest_when_full_and_stays_bounded():
    """A slow consumer (never drains) caps at maxsize, keeping newest events."""
    group_id = uuid4()
    queue = subscribe(group_id=group_id)
    try:
        total = _QUEUE_MAXSIZE * 3
        for seq in range(total):
            await publish(_event(group_id, seq=seq))

        # Never grows past the cap.
        assert queue.qsize() == _QUEUE_MAXSIZE

        # Drop-oldest: the buffer holds the most recent maxsize events.
        seqs = [queue.get_nowait().payload["seq"] for _ in range(queue.qsize())]
        assert seqs == list(range(total - _QUEUE_MAXSIZE, total))
    finally:
        unsubscribe(queue)


async def test_publish_does_not_block_on_full_subscriber():
    """One full (slow) subscriber must not stall delivery to the others."""
    group_id = uuid4()
    slow = subscribe(group_id=group_id)
    fast = subscribe(group_id=group_id)
    try:
        # Fill the slow consumer's queue to the brim; it never drains.
        for seq in range(_QUEUE_MAXSIZE):
            await publish(_event(group_id, seq=seq))
        assert slow.qsize() == _QUEUE_MAXSIZE

        # Drain the fast consumer so it has room, then publish one more.
        while not fast.empty():
            fast.get_nowait()

        # Should return promptly even though `slow` is full.
        await asyncio.wait_for(publish(_event(group_id, seq=9999)), timeout=1.0)

        # Fast subscriber received the newest event...
        assert fast.qsize() == 1
        assert fast.get_nowait().payload["seq"] == 9999
        # ...and the slow one stayed bounded (oldest shed for the newest).
        assert slow.qsize() == _QUEUE_MAXSIZE
    finally:
        unsubscribe(slow)
        unsubscribe(fast)


class _RacyQueue(asyncio.Queue):
    """Queue whose ``put_nowait`` raises QueueFull for the first ``fail_puts``
    calls regardless of room — simulates another producer refilling the freed
    slot in the publish() shed-then-put race (the exact window S4 drops in)."""

    def __init__(self, *a, fail_puts: int = 0, **k):
        super().__init__(*a, **k)
        self._fail_puts = fail_puts

    def put_nowait(self, item):  # type: ignore[override]
        if self._fail_puts > 0:
            self._fail_puts -= 1
            raise asyncio.QueueFull
        return super().put_nowait(item)


async def test_terminal_frame_is_not_dropped_under_producer_race():
    """S4: a run-terminal frame must reach the consumer even when the
    shed-then-put race keeps losing the freed slot — otherwise a run-scoped
    watcher hangs forever with no EOF."""
    group_id = uuid4()
    # Pre-fill so the queue is full, then make the next 3 puts race-fail.
    q = _RacyQueue(maxsize=_QUEUE_MAXSIZE, fail_puts=3)
    for seq in range(_QUEUE_MAXSIZE):
        asyncio.Queue.put_nowait(q, _event(group_id, seq=seq))
    hub._SUBSCRIPTIONS.append(hub._Subscription(queue=q, group_id=group_id))
    try:
        terminal = _event(
            group_id, seq=9001, event_type="simulation.generate.completed"
        )
        await publish(terminal)
        drained = [q.get_nowait() for _ in range(q.qsize())]
        # The terminal frame survived the race and is in the buffer.
        assert any(e.payload["seq"] == 9001 for e in drained)
    finally:
        hub._SUBSCRIPTIONS[:] = [s for s in hub._SUBSCRIPTIONS if s.queue is not q]


async def test_non_terminal_frame_is_dropped_on_lost_race():
    """A mid-run (non-terminal) frame keeps the original best-effort drop: when
    the re-put loses the race it is dropped, not retried (fan-out stays cheap)."""
    group_id = uuid4()
    q = _RacyQueue(maxsize=_QUEUE_MAXSIZE, fail_puts=2)
    for seq in range(_QUEUE_MAXSIZE):
        asyncio.Queue.put_nowait(q, _event(group_id, seq=seq))
    hub._SUBSCRIPTIONS.append(hub._Subscription(queue=q, group_id=group_id))
    try:
        progress = _event(
            group_id, seq=9002, event_type="simulation.generate.progress"
        )
        await publish(progress)  # must not raise / hang
        drained = [q.get_nowait() for _ in range(q.qsize())]
        assert all(e.payload["seq"] != 9002 for e in drained)
    finally:
        hub._SUBSCRIPTIONS[:] = [s for s in hub._SUBSCRIPTIONS if s.queue is not q]


async def test_unsubscribe_cleanup_intact():
    group_id = uuid4()
    queue = subscribe(group_id=group_id)
    assert any(s.queue is queue for s in hub._SUBSCRIPTIONS)
    unsubscribe(queue)
    assert not any(s.queue is queue for s in hub._SUBSCRIPTIONS)
