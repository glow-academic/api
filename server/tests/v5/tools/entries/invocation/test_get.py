"""Tests for get_invocations."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.invocation.create import create_invocation
from app.tools.entries.invocation.get import get_invocations

pytestmark = pytest.mark.asyncio


async def _setup(conn):
    benchmark = await create_benchmark(conn)
    return benchmark


async def test_get_returns_created(conn):
    benchmark = await _setup(conn)
    created = await create_invocation(conn, benchmark_id=benchmark.id)

    results = await get_invocations(conn, [created.id])

    assert len(results) == 1
    assert results[0].id == created.id


async def test_get_returns_base_fields(conn):
    benchmark = await _setup(conn)
    created = await create_invocation(
        conn,
        benchmark_id=benchmark.id,
        use_custom=True,
        position=3,
        mcp=True,
    )

    results = await get_invocations(conn, [created.id])

    assert len(results) == 1
    item = results[0]
    assert item.benchmark_id == benchmark.id
    assert item.use_custom is True
    assert item.position == 3
    assert item.mcp is True
    assert item.generated is True
    assert item.active is True
    assert item.created_at is not None


async def test_get_without_connections_returns_empty_lists(conn):
    benchmark = await _setup(conn)
    created = await create_invocation(conn, benchmark_id=benchmark.id)

    results = await get_invocations(conn, [created.id])

    assert len(results) == 1
    item = results[0]
    assert item.department_ids == []
    assert item.description_ids == []
    assert item.flag_ids == []
    assert item.key_ids == []
    assert item.modality_ids == []
    assert item.model_flag_ids == []
    assert item.model_position_ids == []
    assert item.model_rubric_ids == []
    assert item.model_ids == []
    assert item.name_ids == []
    assert item.quality_ids == []
    assert item.reasoning_level_ids == []
    assert item.temperature_level_ids == []
    assert item.voice_ids == []


async def test_get_with_connections(conn):
    benchmark = await _setup(conn)

    # Use seed data for names_resource
    name_id = await conn.fetchval("SELECT id FROM names_resource LIMIT 1")
    assert name_id is not None, "Seed data must have at least one names_resource row"

    dept_id = await conn.fetchval("SELECT id FROM departments_resource LIMIT 1")
    assert dept_id is not None, (
        "Seed data must have at least one departments_resource row"
    )

    created = await create_invocation(
        conn,
        benchmark_id=benchmark.id,
        name_ids=[name_id],
        department_ids=[dept_id],
    )

    results = await get_invocations(conn, [created.id])

    assert len(results) == 1
    item = results[0]
    assert name_id in item.name_ids
    assert dept_id in item.department_ids


async def test_returns_empty_for_nonexistent_id(conn):
    results = await get_invocations(conn, [nonexistent_id()])

    assert results == []


async def test_get_empty_ids_returns_empty(conn):
    results = await get_invocations(conn, [])

    assert results == []


async def test_get_multiple(conn):
    benchmark = await _setup(conn)
    c1 = await create_invocation(conn, benchmark_id=benchmark.id)
    c2 = await create_invocation(conn, benchmark_id=benchmark.id)

    results = await get_invocations(conn, [c1.id, c2.id])

    result_ids = {r.id for r in results}
    assert c1.id in result_ids
    assert c2.id in result_ids
