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


def _event(group_id, *, seq: int) -> EventEnvelope:
    return EventEnvelope(
        id=f"evt-{seq}",
        event_type="simulation.generate.progress",
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


async def test_unsubscribe_cleanup_intact():
    group_id = uuid4()
    queue = subscribe(group_id=group_id)
    assert any(s.queue is queue for s in hub._SUBSCRIPTIONS)
    unsubscribe(queue)
    assert not any(s.queue is queue for s in hub._SUBSCRIPTIONS)
