"""Tests for search_instructions."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.instructions.create import create_instruction
from app.tools.resources.instructions.search import search_instructions

pytestmark = pytest.mark.asyncio


async def test_finds_created_instruction(conn, redis_client):
    await create_instruction(conn, "search-test-alpha-template", redis_client)

    items = await search_instructions(
        conn, redis_client, search="search-test-alpha-template"
    )

    assert len(items) >= 1
    assert any(i.template == "search-test-alpha-template" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_instruction(conn, "CaseTest-Search-Instruction", redis_client)

    items = await search_instructions(
        conn, redis_client, search="casetest-search-instruction"
    )

    assert any(i.template == "CaseTest-Search-Instruction" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_instructions(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_instruction(conn, f"limit-test-instr-{unique_tag()}", redis_client)

    items = await search_instructions(
        conn, redis_client, search="limit-test-instr-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_instruction(
            conn, f"offset-test-instr-{unique_tag()}", redis_client
        )

    all_items = await search_instructions(
        conn, redis_client, search="offset-test-instr-", limit_count=10
    )
    offset_items = await search_instructions(
        conn, redis_client, search="offset-test-instr-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_instruction(conn, f"exclude-a-instr-{unique_tag()}", redis_client)
    b = await create_instruction(conn, f"exclude-b-instr-{unique_tag()}", redis_client)

    items = await search_instructions(
        conn,
        redis_client,
        search="exclude-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_instructions(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_instruction(conn, f"cache-hit-instr-{unique_tag()}", redis_client)

    items1 = await search_instructions(conn, redis_client, search="cache-hit-instr-")
    items2 = await search_instructions(conn, redis_client, search="cache-hit-instr-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_instruction(conn, f"bypass-instr-{unique_tag()}", redis_client)

    items = await search_instructions(
        conn, redis_client, search="bypass-instr-", bypass_cache=True
    )

    assert len(items) >= 1
