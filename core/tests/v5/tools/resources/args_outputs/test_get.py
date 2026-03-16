"""Tests for get_args_outputs."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.args.create import create_arg
from app.tools.resources.args_outputs.get import get_args_outputs

pytestmark = pytest.mark.asyncio


async def test_gets_created_args_output(conn, redis_client):
    arg = await create_arg(conn, "test-arg", "text", redis_client)
    from app.tools.resources.args_outputs.create import create_args_output

    item = await create_args_output(conn, arg.id, "output-name", redis_client)

    items = await get_args_outputs(conn, [item.id], redis_client)

    assert len(items) == 1
    assert items[0].id == item.id
    assert items[0].args_id == arg.id
    assert items[0].name == "output-name"
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_args_outputs(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_args_outputs(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    arg = await create_arg(conn, "test-arg-cache", "text", redis_client)
    from app.tools.resources.args_outputs.create import create_args_output

    item = await create_args_output(conn, arg.id, "cache-output", redis_client)

    # First call populates cache
    items = await get_args_outputs(conn, [item.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_args_outputs(conn, [item.id], redis_client)
    assert len(items2) == 1
    assert items2[0].id == item.id


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    arg = await create_arg(conn, "test-arg-bypass", "text", redis_client)
    from app.tools.resources.args_outputs.create import create_args_output

    item = await create_args_output(conn, arg.id, "bypass-output", redis_client)

    items = await get_args_outputs(conn, [item.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/args_outputs/get", {"ids": [str(item.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
