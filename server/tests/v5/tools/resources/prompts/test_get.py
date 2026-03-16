"""Tests for get_prompts."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.prompts.create import create_prompt
from app.tools.resources.prompts.get import get_prompts

pytestmark = pytest.mark.asyncio


async def test_gets_created_prompt(conn, redis_client):
    created = await create_prompt(
        conn,
        "You are a helpful assistant.",
        "test-prompt",
        "A test prompt.",
        redis_client,
    )

    items = await get_prompts(conn, [created.id], redis_client)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].system_prompt == "You are a helpful assistant."
    assert items[0].name == "test-prompt"
    assert items[0].description == "A test prompt."
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_prompts(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_prompts(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    created = await create_prompt(
        conn, "Cache prompt content.", "cache-prompt", "Cache test.", redis_client
    )

    # First call populates cache
    items = await get_prompts(conn, [created.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_prompts(conn, [created.id], redis_client)
    assert len(items2) == 1
    assert items2[0].name == "cache-prompt"


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    created = await create_prompt(
        conn, "Bypass prompt content.", "bypass-prompt", "Bypass test.", redis_client
    )

    items = await get_prompts(conn, [created.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/prompts/get", {"ids": [str(created.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
