"""Tests for search_invocations."""

import pytest

from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.invocation.create import create_invocation
from app.tools.entries.invocation.search import search_invocations

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _setup(conn, redis_client):
    benchmark = await create_benchmark(conn, redis_client)
    return benchmark


async def test_search_finds_created(conn, redis_client):
    benchmark = await _setup(conn, redis_client)
    created = await create_invocation(conn, redis_client, benchmark_id=benchmark.id)

    results = await search_invocations(conn, redis_client, benchmark_ids=[benchmark.id])

    result_ids = {r.id for r in results}
    assert created.id in result_ids


async def test_search_filters_by_benchmark(conn, redis_client):
    b1 = await _setup(conn, redis_client)
    b2 = await _setup(conn, redis_client)
    c1 = await create_invocation(conn, redis_client, benchmark_id=b1.id)
    await create_invocation(conn, redis_client, benchmark_id=b2.id)

    results = await search_invocations(conn, redis_client, benchmark_ids=[b1.id])

    result_ids = {r.id for r in results}
    assert c1.id in result_ids
    # b2's invocation should not appear
    for r in results:
        assert r.benchmark_id == b1.id


async def test_search_returns_connections(conn, redis_client):
    benchmark = await _setup(conn, redis_client)

    name_id = await conn.fetchval("SELECT id FROM names_resource LIMIT 1")
    assert name_id is not None, "Seed data must have at least one names_resource row"

    created = await create_invocation(
        conn,
        redis_client, benchmark_id=benchmark.id,
        name_ids=[name_id],
    )

    results = await search_invocations(conn, redis_client, benchmark_ids=[benchmark.id])

    matched = [r for r in results if r.id == created.id]
    assert len(matched) == 1
    assert name_id in matched[0].name_ids


async def test_search_pagination(conn, redis_client):
    benchmark = await _setup(conn, redis_client)
    for _ in range(3):
        await create_invocation(conn, redis_client, benchmark_id=benchmark.id)

    page1 = await search_invocations(
        conn, redis_client, benchmark_ids=[benchmark.id], limit=2, offset=0
    )
    page2 = await search_invocations(
        conn, redis_client, benchmark_ids=[benchmark.id], limit=2, offset=2
    )

    assert len(page1) == 2
    assert len(page2) == 1

    all_ids = {r.id for r in page1} | {r.id for r in page2}
    assert len(all_ids) == 3


async def test_search_no_filters_returns_all(conn, redis_client):
    benchmark = await _setup(conn, redis_client)
    created = await create_invocation(conn, redis_client, benchmark_id=benchmark.id)

    results = await search_invocations(conn, redis_client)

    result_ids = {r.id for r in results}
    assert created.id in result_ids
