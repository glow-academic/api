"""report-21 V2-GAP: the soft_calls cache write-back must participate in the
report-19 HC2 / report-20 V2 write-back deferral.

``create_soft_call`` and ``resolve_soft_call`` used to write their cache via a
DIRECT ``redis.pipeline().setex(...)`` (a comment even said it "reaches past
BatchedRedis"), bypassing ``write_back_row`` — so the SETEX fired IMMEDIATELY,
and a rollback inside a soft-call transaction left a phantom terminal cache row
served from the per-id key (``entry:soft_call:{call_id}``) and the recent-writes
index for the TTL. ``get_soft_call`` / ``search_soft_calls`` would then serve a
status with no backing DB row.

The fix routes both write-backs through ``write_back_row`` (entry="soft_call"),
which defers the SETEX until COMMIT when issued inside
``transaction_with_writeback``. These tests mirror
``tests/utils/cache/test_hedged_row_writeback.py``: a write inside a deferred
transaction that ROLLS BACK leaves NO soft-call cache row; a COMMIT flushes it;
and a write OUTSIDE any transaction stays immediate (unchanged behaviour).

``soft_calls_entry.call_id`` has an FK to ``calls_entry``, so these reuse the
``call_id`` fixture (a real committed call) — same as test_resolve.py.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.resolve import resolve_soft_call
from app.utils.cache.hedged_row import transaction_with_writeback

pytestmark = pytest.mark.asyncio

_SOFT_CALL_RECENT_KEY = "entry:soft_call:recent"


def _row_key(call_id) -> str:
    return f"entry:soft_call:{call_id}"


class _Boom(Exception):
    """Sentinel used to force a transaction rollback."""


async def _read_cached(redis_client, call_id):
    return await redis_client.get(_row_key(call_id))


async def test_create_writeback_discarded_on_rollback(conn, redis_client, call_id):
    """A create_soft_call inside a deferred transaction that ROLLS BACK must
    leave NO phantom soft-call cache row (per-id key and recent-index entry)."""
    with pytest.raises(_Boom):
        async with transaction_with_writeback(conn):
            await create_soft_call(
                conn, redis_client, call_id=call_id, artifact="attempt",
                operation="complete", artifact_id=uuid4(), status="pending",
            )
            # Deferred: the SETEX must NOT have fired yet, mid-transaction.
            assert await _read_cached(redis_client, call_id) is None
            raise _Boom()

    # After rollback: no phantom cache row, and the recent-index has no ref.
    assert await _read_cached(redis_client, call_id) is None
    assert await redis_client.zscore(_SOFT_CALL_RECENT_KEY, str(call_id)) is None


async def test_create_writeback_flushed_on_commit(conn, redis_client, call_id):
    """A create_soft_call inside a deferred transaction that COMMITS flushes the
    write-back so get_soft_call sees it from cache immediately."""
    async with transaction_with_writeback(conn):
        await create_soft_call(
            conn, redis_client, call_id=call_id, artifact="attempt",
            operation="complete", artifact_id=uuid4(), status="pending",
        )
        # Still deferred — not visible while the transaction is open.
        assert await _read_cached(redis_client, call_id) is None

    # After a clean commit the write-back is flushed and readable from cache.
    cached = await get_soft_call(conn, call_id, redis_client)
    assert cached is not None
    assert cached.status == "pending"
    assert cached.call_id == call_id
    assert await redis_client.zscore(_SOFT_CALL_RECENT_KEY, str(call_id)) is not None


async def test_create_writeback_immediate_outside_transaction(
    conn, redis_client, call_id
):
    """No active deferral → create_soft_call's write-back fires immediately
    (unchanged behaviour for writes outside any transaction)."""
    await create_soft_call(
        conn, redis_client, call_id=call_id, artifact="attempt",
        operation="complete", artifact_id=uuid4(), status="pending",
    )
    cached = await get_soft_call(conn, call_id, redis_client)
    assert cached is not None
    assert cached.status == "pending"


async def test_resolve_writeback_discarded_on_rollback(conn, redis_client, call_id):
    """resolve_soft_call (the A4 ack, run INSIDE the caller's transaction) is the
    exact V2-GAP case: its terminal-state write-back must defer to COMMIT. A
    rollback leaves NO phantom terminal cache row."""
    artifact_id = uuid4()
    # Seed a pending row + warm the per-id cache immediately (no deferral active).
    await create_soft_call(
        conn, redis_client, call_id=call_id, artifact="attempt",
        operation="complete", artifact_id=artifact_id, status="pending",
    )
    assert await _read_cached(redis_client, call_id) is not None

    with pytest.raises(_Boom):
        async with transaction_with_writeback(conn):
            resolved = await resolve_soft_call(
                conn, redis_client, call_id=call_id, artifact="attempt",
                operation="complete", artifact_id=artifact_id, accept=True,
            )
            assert resolved is not None
            assert resolved.status == "accepted"
            # The terminal write-back is deferred: the cached row is still the
            # pre-resolve 'pending' state, NOT a phantom 'accepted'.
            mid = await get_soft_call(conn, call_id, redis_client)
            assert mid is not None
            assert mid.status == "pending"
            raise _Boom()

    # After rollback: the cache still serves the pre-resolve 'pending' status —
    # no phantom 'accepted' terminal row was flushed.
    after = await get_soft_call(conn, call_id, redis_client)
    assert after is not None
    assert after.status == "pending"


async def test_resolve_writeback_flushed_on_commit(conn, redis_client, call_id):
    """resolve_soft_call's terminal write-back is flushed on a clean commit so
    get_soft_call sees the terminal status from cache."""
    artifact_id = uuid4()
    await create_soft_call(
        conn, redis_client, call_id=call_id, artifact="attempt",
        operation="complete", artifact_id=artifact_id, status="pending",
    )

    async with transaction_with_writeback(conn):
        resolved = await resolve_soft_call(
            conn, redis_client, call_id=call_id, artifact="attempt",
            operation="complete", artifact_id=artifact_id, accept=True,
        )
        assert resolved is not None
        # Still deferred mid-transaction: cache shows the old 'pending'.
        mid = await get_soft_call(conn, call_id, redis_client)
        assert mid is not None
        assert mid.status == "pending"

    # After commit the terminal write-back is flushed.
    after = await get_soft_call(conn, call_id, redis_client)
    assert after is not None
    assert after.status == "accepted"
