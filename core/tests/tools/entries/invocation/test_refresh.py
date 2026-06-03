"""Tests for refresh_invocations."""

import pytest
from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.invocation.create import create_invocation
from app.tools.entries.invocation.get import get_invocations
from app.tools.entries.invocation.refresh import refresh_invocations

pytestmark = pytest.mark.asyncio


async def _invocation(conn, redis_client, **overrides):
    benchmark = await create_benchmark(conn, redis_client)
    defaults = dict(benchmark_id=benchmark.id)
    defaults.update(overrides)
    result = await create_invocation(conn, redis_client, **defaults)
    return result, benchmark


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_invocation_appears_after_refresh(conn, redis_client):
    created = _created(await _invocation(conn, redis_client))
    lookup_id = created.id

    await refresh_invocations(conn)
    items = await get_invocations(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_invocation_is_visible_before_refresh(conn, redis_client):
    # get_invocations reads the base invocation_entry table (not the MV), so a
    # freshly created row is immediately visible even with bypass_cache=True —
    # no refresh required. Refresh only repopulates invocation_mv (see the
    # MV-population test below).
    created = _created(await _invocation(conn, redis_client))
    lookup_id = created.id

    items = await get_invocations(
        conn, ids=[lookup_id], redis=redis_client, bypass_cache=True
    )

    assert len(items) == 1
    assert items[0].id == lookup_id


async def test_invocation_mv_populated_only_after_refresh(conn, redis_client):
    # The materialized view invocation_mv (consumed by the bundle/view path) is
    # NOT updated by create; it only reflects the new row after refresh.
    created = _created(await _invocation(conn, redis_client))
    lookup_id = created.id

    in_mv_before = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM invocation_mv WHERE invocation_entry_id = $1)",
        lookup_id,
    )
    assert in_mv_before is False

    await refresh_invocations(conn)

    in_mv_after = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM invocation_mv WHERE invocation_entry_id = $1)",
        lookup_id,
    )
    assert in_mv_after is True


async def test_refresh_is_idempotent(conn):
    await refresh_invocations(conn)
    await refresh_invocations(conn)

    assert True
