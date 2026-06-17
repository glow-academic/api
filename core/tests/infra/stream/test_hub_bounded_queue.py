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


async def test_buffered_terminal_is_not_evicted_to_make_room():
    """report-19 HUB1: when a full queue must make room for a new mid-run frame,
    an ALREADY-BUFFERED terminal must NOT be the one evicted — the oldest
    DROPPABLE frame is shed instead. The prior logic shed the oldest frame
    blindly, which could drop an unread buffered terminal → a run-scoped watcher
    hangs with no EOF (S4)."""
    group_id = uuid4()
    queue = subscribe(group_id=group_id)
    try:
        # Oldest buffered frame is a TERMINAL, then fill the rest with progress.
        await publish(
            _event(group_id, seq=0, event_type="simulation.generate.completed")
        )
        for seq in range(1, _QUEUE_MAXSIZE):
            await publish(_event(group_id, seq=seq))
        assert queue.qsize() == _QUEUE_MAXSIZE

        # A new mid-run frame arrives on the full queue.
        await publish(_event(group_id, seq=9999))

        drained = [queue.get_nowait() for _ in range(queue.qsize())]
        seqs = [e.payload["seq"] for e in drained]
        # The buffered terminal (seq 0) SURVIVED; the oldest droppable (seq 1)
        # was shed; the newest landed; FIFO order preserved; still bounded.
        assert len(seqs) == _QUEUE_MAXSIZE
        assert 0 in seqs, "buffered terminal must not be evicted"
        assert 1 not in seqs, "oldest droppable should be the victim"
        assert 9999 in seqs
        assert seqs == sorted(seqs), "survivors keep FIFO order"
    finally:
        unsubscribe(queue)


async def test_incoming_droppable_dropped_when_queue_is_all_terminals():
    """If every buffered frame is non-droppable, an incoming DROPPABLE frame is
    the one dropped — the load-bearing terminals are all kept."""
    group_id = uuid4()
    queue = subscribe(group_id=group_id)
    try:
        for seq in range(_QUEUE_MAXSIZE):
            await publish(
                _event(group_id, seq=seq, event_type="simulation.generate.completed")
            )
        assert queue.qsize() == _QUEUE_MAXSIZE

        await publish(_event(group_id, seq=9999))  # droppable

        drained = [queue.get_nowait() for _ in range(queue.qsize())]
        seqs = [e.payload["seq"] for e in drained]
        # All terminals kept; the incoming droppable was dropped.
        assert seqs == list(range(_QUEUE_MAXSIZE))
        assert 9999 not in seqs
    finally:
        unsubscribe(queue)


async def test_unsubscribe_cleanup_intact():
    group_id = uuid4()
    queue = subscribe(group_id=group_id)
    assert any(s.queue is queue for s in hub._SUBSCRIPTIONS)
    unsubscribe(queue)
    assert not any(s.queue is queue for s in hub._SUBSCRIPTIONS)
