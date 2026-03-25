"""Tests for search_args_outputs."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.args.create import create_arg
from app.tools.resources.args_outputs.create import create_args_output
from app.tools.resources.args_outputs.search import search_args_outputs

pytestmark = pytest.mark.asyncio


async def test_finds_created_args_output(conn, redis_client):
    arg = await create_arg(conn, f"parent-arg-{unique_tag()}", "string", redis_client)
    await create_args_output(conn, arg.id, "search-test-alpha", redis_client)

    items = await search_args_outputs(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1
    assert any(i.name == "search-test-alpha" for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    arg = await create_arg(conn, f"parent-arg-{unique_tag()}", "string", redis_client)
    await create_args_output(conn, arg.id, "CaseTest-ArgsOutput", redis_client)

    items = await search_args_outputs(conn, redis_client, search="casetest-argsoutput")

    assert any(i.name == "CaseTest-ArgsOutput" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_args_outputs(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    arg = await create_arg(conn, f"parent-arg-{unique_tag()}", "string", redis_client)
    for i in range(5):
        await create_args_output(conn, arg.id, f"limit-ao-{unique_tag()}", redis_client)

    items = await search_args_outputs(
        conn, redis_client, search="limit-ao-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    arg = await create_arg(conn, f"parent-arg-{unique_tag()}", "string", redis_client)
    for i in range(3):
        await create_args_output(
            conn, arg.id, f"offset-ao-{unique_tag()}", redis_client
        )

    all_items = await search_args_outputs(
        conn, redis_client, search="offset-ao-", limit_count=10
    )
    offset_items = await search_args_outputs(
        conn, redis_client, search="offset-ao-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    arg = await create_arg(conn, f"parent-arg-{unique_tag()}", "string", redis_client)
    a = await create_args_output(
        conn, arg.id, f"exclude-aoa-{unique_tag()}", redis_client
    )
    b = await create_args_output(
        conn, arg.id, f"exclude-aob-{unique_tag()}", redis_client
    )

    items = await search_args_outputs(
        conn,
        redis_client,
        search="exclude-ao",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_args_outputs(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    arg = await create_arg(conn, f"parent-arg-{unique_tag()}", "string", redis_client)
    await create_args_output(conn, arg.id, f"cache-hit-ao-{unique_tag()}", redis_client)

    items1 = await search_args_outputs(conn, redis_client, search="cache-hit-ao-")
    items2 = await search_args_outputs(conn, redis_client, search="cache-hit-ao-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    arg = await create_arg(conn, f"parent-arg-{unique_tag()}", "string", redis_client)
    await create_args_output(conn, arg.id, f"bypass-ao-{unique_tag()}", redis_client)

    items = await search_args_outputs(
        conn, redis_client, search="bypass-ao-", bypass_cache=True
    )

    assert len(items) >= 1
