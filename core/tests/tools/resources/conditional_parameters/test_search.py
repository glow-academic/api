"""Tests for search_conditional_parameters."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.conditional_parameters.create import (
    create_conditional_parameter,
)
from app.tools.resources.conditional_parameters.search import (
    search_conditional_parameters,
)
from app.tools.resources.parameters.create import create_parameter

pytestmark = pytest.mark.asyncio


async def _make(conn, redis_client, name: str = ""):
    """Helper: create a parameter then a conditional_parameter referencing it."""
    param = await create_parameter(conn, redis_client, name=name or f"p-{unique_tag()}")
    return await create_conditional_parameter(conn, param.id, redis_client)


async def test_finds_created_conditional_parameter(conn, redis_client):
    created = await _make(conn, redis_client)

    items = await search_conditional_parameters(conn, redis_client)

    assert len(items) >= 1
    assert any(i.id == created.id for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    created = await _make(conn, redis_client)

    # Search by partial UUID text (case insensitive)
    partial = str(created.id)[:8].upper()
    items = await search_conditional_parameters(conn, redis_client, search=partial)

    assert any(i.id == created.id for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_conditional_parameters(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for _ in range(5):
        await _make(conn, redis_client)

    items = await search_conditional_parameters(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for _ in range(3):
        await _make(conn, redis_client)

    all_items = await search_conditional_parameters(conn, redis_client, limit_count=100)
    offset_items = await search_conditional_parameters(
        conn, redis_client, limit_count=100, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await _make(conn, redis_client)
    b = await _make(conn, redis_client)

    items = await search_conditional_parameters(
        conn,
        redis_client,
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_conditional_parameters(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await _make(conn, redis_client)

    items1 = await search_conditional_parameters(conn, redis_client)
    items2 = await search_conditional_parameters(conn, redis_client)

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await _make(conn, redis_client)

    items = await search_conditional_parameters(conn, redis_client, bypass_cache=True)

    assert len(items) >= 1
