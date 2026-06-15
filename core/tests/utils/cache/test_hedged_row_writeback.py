"""HC2 (report-19): write-backs issued inside ``transaction_with_writeback``
must defer to AFTER the Postgres transaction commits — a rollback must leave no
phantom cache row, while a commit must flush the write-back.
"""

import uuid

import pytest

from app.utils.cache.hedged_row import (
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
