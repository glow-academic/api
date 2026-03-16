"""Tests for search_artifacts."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.artifacts.create import create_artifact
from app.tools.resources.artifacts.search import search_artifacts

pytestmark = pytest.mark.asyncio


async def test_finds_created_artifact(conn, redis_client):
    await create_artifact(conn, f"search-test-{unique_tag()}", redis_client)

    items = await search_artifacts(conn, redis_client, search="search-test-")

    assert len(items) >= 1


async def test_search_is_case_insensitive(conn, redis_client):
    tag = unique_tag()
    await create_artifact(conn, f"CaseArt-{tag}", redis_client)

    items = await search_artifacts(conn, redis_client, search=f"caseart-{tag}")

    assert len(items) >= 1


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_artifacts(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_artifact(conn, f"limit-art-{unique_tag()}", redis_client)

    items = await search_artifacts(
        conn, redis_client, search="limit-art-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    tag = unique_tag()
    for i in range(3):
        await create_artifact(conn, f"offset-art-{tag}-{i}", redis_client)

    all_items = await search_artifacts(
        conn, redis_client, search=f"offset-art-{tag}", limit_count=10
    )
    offset_items = await search_artifacts(
        conn, redis_client, search=f"offset-art-{tag}", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    tag = unique_tag()
    a = await create_artifact(conn, f"exclude-a-{tag}", redis_client)
    b = await create_artifact(conn, f"exclude-b-{tag}", redis_client)

    items = await search_artifacts(
        conn,
        redis_client,
        search="exclude-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_artifacts(conn, redis_client, limit_count=0)

    assert items == []


async def test_bypass_cache(conn, redis_client):
    await create_artifact(conn, f"bypass-art-{unique_tag()}", redis_client)

    items = await search_artifacts(
        conn, redis_client, search="bypass-art-", bypass_cache=True
    )

    assert len(items) >= 1
