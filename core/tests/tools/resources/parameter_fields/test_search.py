"""Tests for search_parameter_fields."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.fields.create import create_field
from app.tools.resources.parameter_fields.create import create_parameter_field
from app.tools.resources.parameter_fields.search import (
    search_parameter_fields,
)
from app.tools.resources.parameters.create import create_parameter

pytestmark = pytest.mark.asyncio


async def _create_parameter_field_with_deps(conn, redis_client):
    """Helper: create a parameter + field + parameter_field."""
    parameter = await create_parameter(conn, redis_client, name=f"param-{unique_tag()}")
    field = await create_field(
        conn, name=f"field-{unique_tag()}", description="", redis=redis_client
    )
    pf = await create_parameter_field(
        conn, field.id, redis_client, parameter_id=parameter.id
    )
    return pf


async def test_finds_created_parameter_field(conn, redis_client):
    pf = await _create_parameter_field_with_deps(conn, redis_client)

    items = await search_parameter_fields(conn, redis_client, limit_count=1000)

    ids = [i.id for i in items]
    assert pf.id in ids


async def test_respects_limit(conn, redis_client):
    for _ in range(3):
        await _create_parameter_field_with_deps(conn, redis_client)

    items = await search_parameter_fields(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for _ in range(3):
        await _create_parameter_field_with_deps(conn, redis_client)

    all_items = await search_parameter_fields(conn, redis_client, limit_count=1000)
    offset_items = await search_parameter_fields(
        conn, redis_client, limit_count=1000, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await _create_parameter_field_with_deps(conn, redis_client)
    b = await _create_parameter_field_with_deps(conn, redis_client)

    items = await search_parameter_fields(
        conn, redis_client, limit_count=1000, exclude_ids=[a.id]
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_parameter_fields(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await _create_parameter_field_with_deps(conn, redis_client)

    items1 = await search_parameter_fields(conn, redis_client, limit_count=1000)
    items2 = await search_parameter_fields(conn, redis_client, limit_count=1000)

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await _create_parameter_field_with_deps(conn, redis_client)

    items = await search_parameter_fields(
        conn, redis_client, limit_count=1000, bypass_cache=True
    )

    assert len(items) >= 1
