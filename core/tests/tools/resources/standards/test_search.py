"""Tests for search_standards."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.standard_groups.create import create_standard_group
from app.tools.resources.standards.create import create_standard
from app.tools.resources.standards.search import search_standards

pytestmark = pytest.mark.asyncio


async def _make_group(conn, redis_client, suffix=""):
    return await create_standard_group(
        conn,
        name=f"sg-{suffix or unique_tag()}",
        short_name=f"SG-{suffix or unique_tag()}",
        description="test group",
        points=100,
        pass_points=70,
        redis=redis_client,
    )


async def _make_standard(conn, redis_client, name, group_id):
    return await create_standard(
        conn,
        name=name,
        description="test standard",
        points=10,
        standard_group_id=group_id,
        redis=redis_client,
    )


async def test_finds_created_standard(conn, redis_client):
    group = await _make_group(conn, redis_client)
    await _make_standard(conn, redis_client, "search-test-alpha", group.id)

    items = await search_standards(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1
    assert any(i.name == "search-test-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    group = await _make_group(conn, redis_client)
    await _make_standard(conn, redis_client, "CaseTest-Standard", group.id)

    items = await search_standards(conn, redis_client, search="casetest-standard")

    assert any(i.name == "CaseTest-Standard" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_standards(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    group = await _make_group(conn, redis_client)
    for i in range(5):
        await _make_standard(conn, redis_client, f"limit-std-{unique_tag()}", group.id)

    items = await search_standards(
        conn, redis_client, search="limit-std-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    group = await _make_group(conn, redis_client)
    for i in range(3):
        await _make_standard(conn, redis_client, f"offset-std-{unique_tag()}", group.id)

    all_items = await search_standards(
        conn, redis_client, search="offset-std-", limit_count=10
    )
    offset_items = await search_standards(
        conn, redis_client, search="offset-std-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    group = await _make_group(conn, redis_client)
    a = await _make_standard(conn, redis_client, f"exclude-a-{unique_tag()}", group.id)
    b = await _make_standard(conn, redis_client, f"exclude-b-{unique_tag()}", group.id)

    items = await search_standards(
        conn,
        redis_client,
        search="exclude-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_filters_by_standard_group_ids(conn, redis_client):
    group_a = await _make_group(conn, redis_client, f"grp-a-{unique_tag()}")
    group_b = await _make_group(conn, redis_client, f"grp-b-{unique_tag()}")
    tag = unique_tag()
    await _make_standard(conn, redis_client, f"sg-filter-{tag}-a", group_a.id)
    await _make_standard(conn, redis_client, f"sg-filter-{tag}-b", group_b.id)

    items = await search_standards(
        conn,
        redis_client,
        search=f"sg-filter-{tag}",
        standard_group_ids=[group_a.id],
    )

    assert len(items) >= 1
    assert all(i.standard_group_id == group_a.id for i in items)


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_standards(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    group = await _make_group(conn, redis_client)
    await _make_standard(conn, redis_client, f"cache-hit-{unique_tag()}", group.id)

    items1 = await search_standards(conn, redis_client, search="cache-hit-")
    items2 = await search_standards(conn, redis_client, search="cache-hit-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    group = await _make_group(conn, redis_client)
    await _make_standard(conn, redis_client, f"bypass-{unique_tag()}", group.id)

    items = await search_standards(
        conn, redis_client, search="bypass-", bypass_cache=True
    )

    assert len(items) >= 1
