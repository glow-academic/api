"""Tests for search_emails."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.emails.create import create_email
from app.tools.resources.emails.search import search_emails

pytestmark = pytest.mark.asyncio


async def test_finds_created_email(conn, redis_client):
    await create_email(conn, f"search-test-{unique_tag()}@example.com", redis_client)

    items = await search_emails(conn, redis_client, search="search-test-")

    assert len(items) >= 1
    assert any("search-test-" in i.email for i in items)


async def test_search_is_case_insensitive(conn, redis_client):
    unique = unique_tag()
    await create_email(conn, f"CaseTest-{unique}@Example.COM", redis_client)

    items = await search_emails(conn, redis_client, search=f"casetest-{unique}")

    assert len(items) >= 1


async def test_returns_empty_for_no_match(conn, redis_client):
    items = await search_emails(
        conn, redis_client, search="zzz-no-match-zzz-" + unique_tag()
    )

    assert items == []


async def test_respects_limit(conn, redis_client):
    for i in range(5):
        await create_email(
            conn, f"limit-test-email-{unique_tag()}@example.com", redis_client
        )

    items = await search_emails(
        conn, redis_client, search="limit-test-email-", limit_count=2
    )

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for i in range(3):
        await create_email(
            conn, f"offset-test-email-{unique_tag()}@example.com", redis_client
        )

    all_items = await search_emails(
        conn, redis_client, search="offset-test-email-", limit_count=10
    )
    offset_items = await search_emails(
        conn,
        redis_client,
        search="offset-test-email-",
        limit_count=10,
        offset_count=1,
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await create_email(conn, f"exclude-a-{unique_tag()}@example.com", redis_client)
    b = await create_email(conn, f"exclude-b-{unique_tag()}@example.com", redis_client)

    items = await search_emails(
        conn, redis_client, search="exclude-", exclude_ids=[a.id]
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_emails(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await create_email(conn, f"cache-hit-{unique_tag()}@example.com", redis_client)

    items1 = await search_emails(conn, redis_client, search="cache-hit-")
    items2 = await search_emails(conn, redis_client, search="cache-hit-")

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await create_email(conn, f"bypass-{unique_tag()}@example.com", redis_client)

    items = await search_emails(conn, redis_client, search="bypass-", bypass_cache=True)

    assert len(items) >= 1
