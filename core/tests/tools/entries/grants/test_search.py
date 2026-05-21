"""Tests for search_grants."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.grants.create import create_grant
from app.tools.entries.grants.search import search_grants
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    result = await create_grant(conn, redis_client, session_id=session.id)
    return result, session


async def test_finds_created_entry(conn, redis_client, profile_id):
    result, session = await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW grants_mv")

    items = await search_grants(conn, redis_client, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_session_id(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW grants_mv")

    items = await search_grants(conn, redis_client, session_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, redis_client, profile_id):
    result, session = await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW grants_mv")

    items = await search_grants(conn, redis_client, session_ids=[session.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await _setup(conn, redis_client, profile_id)
    await conn.execute("REFRESH MATERIALIZED VIEW grants_mv")

    items = await search_grants(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    result, session = await _setup(conn, redis_client, profile_id)

    items = await search_grants(conn, redis_client, session_ids=[session.id], bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
