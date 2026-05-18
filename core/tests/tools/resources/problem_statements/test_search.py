"""Tests for search_problem_statements."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.problem_statements.create import (
    create_problem_statement,
)
from app.tools.resources.problem_statements.search import (
    search_problem_statements,
)

pytestmark = pytest.mark.asyncio


async def test_finds_created_problem_statement(conn, redis_client):
    await create_problem_statement(
        conn, "search-test-ps-alpha", "The problem statement text", redis_client
    )

    items = await search_problem_statements(
        conn, redis_client, search="search-test-ps-alpha"
    )

    assert len(items) >= 1
    assert any(i.name == "search-test-ps-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_problem_statement(
        conn, "CaseTest-Search-PS", "Problem text", redis_client
    )

    items = await search_problem_statements(
        conn, redis_client, search="casetest-search-ps"
    )

    assert any(i.name == "CaseTest-Search-PS" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_problem_statements(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_problem_statement(
            conn,
            f"limit-test-ps-{unique_tag()}",
            "problem text",
            redis_client,
        )

    items = await search_problem_statements(
        conn, redis_client, search="limit-test-ps-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_problem_statement(
            conn,
            f"offset-test-ps-{unique_tag()}",
            "problem text",
            redis_client,
        )

    all_items = await search_problem_statements(
        conn, redis_client, search="offset-test-ps-", limit_count=10
    )
    offset_items = await search_problem_statements(
        conn, redis_client, search="offset-test-ps-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_problem_statement(
        conn, f"exclude-a-ps-{unique_tag()}", "text a", redis_client
    )
    b = await create_problem_statement(
        conn, f"exclude-b-ps-{unique_tag()}", "text b", redis_client
    )

    items = await search_problem_statements(
        conn, redis_client, search="exclude-", exclude_ids=[a.id]
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_problem_statements(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_problem_statement(
        conn, f"cache-hit-ps-{unique_tag()}", "text", redis_client
    )

    items1 = await search_problem_statements(conn, redis_client, search="cache-hit-ps-")
    items2 = await search_problem_statements(conn, redis_client, search="cache-hit-ps-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_problem_statement(
        conn, f"bypass-ps-{unique_tag()}", "text", redis_client
    )

    items = await search_problem_statements(
        conn, redis_client, search="bypass-ps-", bypass_cache=True
    )

    assert len(items) >= 1
