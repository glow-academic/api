"""Tests for search_model_flags."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.flags.create import create_flag
from app.tools.resources.model_flags.create import create_model_flag
from app.tools.resources.model_flags.search import search_model_flags
from app.tools.resources.models.create import create_model

pytestmark = pytest.mark.asyncio


async def _create_model_flag_with_deps(conn, redis_client, flag_name: str):
    """Helper: create a model + flag + model_flag."""
    model = await create_model(conn, value=f"model-{unique_tag()}", redis=redis_client)
    flag = await create_flag(
        conn, name=flag_name, description="", icon="", redis=redis_client
    )
    mf = await create_model_flag(conn, model.id, flag.id, redis_client)
    return mf


async def test_finds_created_model_flag(conn, redis_client):
    await _create_model_flag_with_deps(conn, redis_client, "search-test-alpha")

    items = await search_model_flags(conn, redis_client, search="search-test-alpha")

    assert len(items) >= 1


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_model_flags(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(3):
        await _create_model_flag_with_deps(
            conn, redis_client, f"limit-test-{unique_tag()}"
        )

    items = await search_model_flags(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_excludes_ids(conn, redis_client):
    a = await _create_model_flag_with_deps(
        conn, redis_client, f"exclude-a-{unique_tag()}"
    )
    b = await _create_model_flag_with_deps(
        conn, redis_client, f"exclude-b-{unique_tag()}"
    )

    items = await search_model_flags(
        conn,
        redis_client,
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_model_flags(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await _create_model_flag_with_deps(conn, redis_client, f"cache-hit-{unique_tag()}")

    items1 = await search_model_flags(conn, redis_client)
    items2 = await search_model_flags(conn, redis_client)

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await _create_model_flag_with_deps(conn, redis_client, f"bypass-{unique_tag()}")

    items = await search_model_flags(conn, redis_client, bypass_cache=True)

    assert len(items) >= 1
