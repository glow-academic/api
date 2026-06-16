"""HC2 (report-19): write-backs issued inside ``transaction_with_writeback``
must defer to AFTER the Postgres transaction commits — a rollback must leave no
phantom cache row, while a commit must flush the write-back.
"""

import uuid

import pytest

from app.utils.async_tasks import schedule_background, wait_for_pending
from app.utils.cache.hedged_row import (
    clear_writeback_deferral,
    read_back_row,
    transaction_with_writeback,
    write_back_row,
)

pytestmark = pytest.mark.asyncio


class _Boom(Exception):
    """Sentinel used to force a transaction rollback."""


async def test_writeback_discarded_on_rollback(conn, redis_client):
    rid = str(uuid.uuid4())
    row = {"id": rid, "chat_id": rid, "marker": "rollback"}

    with pytest.raises(_Boom):
        async with transaction_with_writeback(conn):
            await write_back_row(redis_client, "hc2_test", rid, row)
            # Deferred: the SETEX must NOT have fired yet, mid-transaction.
            assert await read_back_row(redis_client, "hc2_test", rid) is None
            raise _Boom()

    # After rollback: no phantom cache row survives.
    assert await read_back_row(redis_client, "hc2_test", rid) is None


async def test_writeback_flushed_on_commit(conn, redis_client):
    rid = str(uuid.uuid4())
    row = {"id": rid, "chat_id": rid, "marker": "commit"}

    async with transaction_with_writeback(conn):
        await write_back_row(redis_client, "hc2_test", rid, row)
        # Still deferred — not visible while the transaction is open.
        assert await read_back_row(redis_client, "hc2_test", rid) is None

    # After a clean commit the write-back is flushed and visible.
    cached = await read_back_row(redis_client, "hc2_test", rid)
    assert cached is not None
    assert cached["marker"] == "commit"


async def test_writeback_immediate_outside_transaction(conn, redis_client):
    # No active deferral → write_back_row keeps its original immediate behaviour.
    rid = str(uuid.uuid4())
    await write_back_row(
        redis_client, "hc2_test", rid, {"id": rid, "marker": "immediate"}
    )
    cached = await read_back_row(redis_client, "hc2_test", rid)
    assert cached is not None
    assert cached["marker"] == "immediate"


async def test_nested_savepoint_flushes_once_at_outer_commit(conn, redis_client):
    """A nested ``transaction_with_writeback`` (asyncpg SAVEPOINT) must NOT flush
    on its own release — only the outermost block flushes, after the real commit.
    """
    outer_id = str(uuid.uuid4())
    inner_id = str(uuid.uuid4())

    async with transaction_with_writeback(conn):
        await write_back_row(
            redis_client, "hc2_test", outer_id, {"id": outer_id, "marker": "outer"}
        )
        async with transaction_with_writeback(conn):
            await write_back_row(
                redis_client, "hc2_test", inner_id, {"id": inner_id, "marker": "inner"}
            )
        # Inner savepoint released, but its write-back must still be deferred —
        # a savepoint release is not a durable commit.
        assert await read_back_row(redis_client, "hc2_test", inner_id) is None

    # After the outermost commit, BOTH write-backs are flushed.
    assert (await read_back_row(redis_client, "hc2_test", outer_id)) is not None
    assert (await read_back_row(redis_client, "hc2_test", inner_id)) is not None


async def test_background_task_does_not_inherit_deferral(conn, redis_client):
    """report-20 V2: a fire-and-forget task spawned INSIDE a deferred
    transaction must NOT inherit the parent's pending-queue. asyncio copies the
    context into the task, so without the ``schedule_background`` reset the
    task's write-back would enqueue into a queue the parent flushes/discards on
    its own boundary — silently losing the write-back (or flushing a phantom
    before the task's own write commits). The bg write-back must fire
    IMMEDIATELY instead.
    """
    bg_id = str(uuid.uuid4())
    deferred_id = str(uuid.uuid4())

    async def _bg() -> None:
        # Runs with the parent context copied in; the spawner reset the
        # deferral so this write-back is immediate.
        await write_back_row(redis_client, "hc2_test", bg_id, {"id": bg_id})

    async with transaction_with_writeback(conn):
        await write_back_row(redis_client, "hc2_test", deferred_id, {"id": deferred_id})
        task = schedule_background(_bg(), label="hc2_bg_leak_test")
        await task  # let the bg task complete while the txn is still open

        # The bg task's write-back fired immediately (not deferred)...
        assert await read_back_row(redis_client, "hc2_test", bg_id) is not None
        # ...while the parent's own write-back is still deferred.
        assert await read_back_row(redis_client, "hc2_test", deferred_id) is None

    # Parent commit flushes only the parent's write-back; bg one already there.
    assert await read_back_row(redis_client, "hc2_test", deferred_id) is not None
    assert await read_back_row(redis_client, "hc2_test", bg_id) is not None
    await wait_for_pending(timeout=2.0)


async def test_clear_writeback_deferral_is_idempotent_without_active_txn():
    """``clear_writeback_deferral`` is safe to call with no deferral active —
    a subsequent immediate write path is unaffected (no exception)."""
    clear_writeback_deferral()
    clear_writeback_deferral()  # idempotent
