"""Tests for create_invocation."""

import pytest

from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.benchmark.get import get_benchmarks
from app.tools.entries.benchmark.refresh import refresh_benchmark
from app.tools.entries.invocation.create import create_invocation

pytestmark = pytest.mark.asyncio


async def _invocation(conn, redis_client, **overrides):
    benchmark = await create_benchmark(conn, redis_client)
    defaults = dict(benchmark_id=benchmark.id)
    defaults.update(overrides)
    result = await create_invocation(conn, redis_client, **defaults)
    return result, benchmark


async def test_returns_id(conn, redis_client):
    result, _ = await _invocation(conn, redis_client)

    assert result.id is not None


async def test_row_exists(conn, redis_client):
    result, benchmark = await _invocation(conn, redis_client)

    row = await conn.fetchrow(
        "SELECT benchmark_id FROM invocation_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["benchmark_id"] == benchmark.id


async def test_passes_mcp_flag(conn, redis_client):
    result, _ = await _invocation(conn, redis_client, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM invocation_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True


async def test_invalidates_stale_benchmark_invocation_ids_cache(conn, redis_client):
    """Regression: creating an invocation must invalidate the parent ``benchmark`` cache.

    ``create_benchmark`` seeds the ``benchmark`` write-back row with empty
    ``invocation_entry_ids`` (the real list is owned by ``invocation_entry``
    rows via ``benchmark_mv``). A cached ``get_benchmarks`` read before the
    invocation exists would prime that empty row; without invalidation in
    ``create_invocation`` the next read returns a stale empty
    ``invocation_entry_ids`` even after the MV is refreshed. Mirrors the #163
    groups/group_names stale-name bug.
    """
    benchmark = await create_benchmark(conn, redis_client)

    # Prime the cache with the create-time row (empty invocation_entry_ids).
    primed = await get_benchmarks(conn, [benchmark.id], redis_client)
    assert primed and primed[0].invocation_entry_ids == []

    # Separate primitive sets the real value.
    invocation = await create_invocation(conn, redis_client, benchmark_id=benchmark.id)
    await refresh_benchmark(conn)

    # Post-fix: cache was invalidated, so this rehydrates from benchmark_mv.
    refreshed = await get_benchmarks(conn, [benchmark.id], redis_client)
    assert refreshed
    assert invocation.id in refreshed[0].invocation_entry_ids
