"""Tests for get_documents."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.documents.create import create_document
from app.tools.resources.documents.get import get_documents

pytestmark = pytest.mark.asyncio


async def test_gets_created_document(conn, redis_client):
    created = await create_document(
        conn, redis_client, name="test-doc", description="desc"
    )

    items = await get_documents(conn, [created.id], redis_client)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].name == "test-doc"
    assert items[0].description == "desc"
    assert items[0].file_id is None
    assert items[0].text_id is None
    assert items[0].template is False
    assert items[0].active is True


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_documents(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_documents(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    created = await create_document(conn, redis_client, name="test-doc-cache")

    # First call populates cache
    items = await get_documents(conn, [created.id], redis_client)
    assert len(items) == 1

    # Second call serves from cache
    items2 = await get_documents(conn, [created.id], redis_client)
    assert len(items2) == 1
    assert items2[0].id == created.id


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    created = await create_document(conn, redis_client, name="test-doc-bypass")

    items = await get_documents(conn, [created.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/documents/get", {"ids": [str(created.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
