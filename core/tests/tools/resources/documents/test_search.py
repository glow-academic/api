"""Tests for search_documents."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.documents.create import create_document
from app.tools.resources.documents.search import search_documents

pytestmark = pytest.mark.asyncio


async def test_finds_created_document(conn, redis_client):
    doc = await create_document(
        conn, redis_client, name="search-doc-alpha", description="desc"
    )

    items = await search_documents(conn, redis_client, search="search-doc-alpha")

    assert len(items) >= 1
    assert any(i.id == doc.id for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    await create_document(
        conn, redis_client, name="CaseTest-DocSearch", description="desc"
    )

    items = await search_documents(conn, redis_client, search="casetest-docsearch")

    assert any(i.name == "CaseTest-DocSearch" for i in items)


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_documents(
        conn, redis_client, search="zzz-no-doc-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_document(
            conn, redis_client, name=f"limit-doc-{unique_tag()}", description=""
        )

    items = await search_documents(
        conn, redis_client, search="limit-doc-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_document(
            conn, redis_client, name=f"offset-doc-{unique_tag()}", description=""
        )

    all_items = await search_documents(
        conn, redis_client, search="offset-doc-", limit_count=10
    )
    offset_items = await search_documents(
        conn, redis_client, search="offset-doc-", limit_count=10, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_document(
        conn, redis_client, name=f"exclude-doc-a-{unique_tag()}", description=""
    )
    b = await create_document(
        conn, redis_client, name=f"exclude-doc-b-{unique_tag()}", description=""
    )

    items = await search_documents(
        conn,
        redis_client,
        search="exclude-doc-",
        exclude_ids=[a.id],
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_documents(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_document(
        conn, redis_client, name=f"cache-doc-{unique_tag()}", description=""
    )

    items1 = await search_documents(conn, redis_client, search="cache-doc-")
    items2 = await search_documents(conn, redis_client, search="cache-doc-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_document(
        conn, redis_client, name=f"bypass-doc-{unique_tag()}", description=""
    )

    items = await search_documents(
        conn, redis_client, search="bypass-doc-", bypass_cache=True
    )

    assert len(items) >= 1
