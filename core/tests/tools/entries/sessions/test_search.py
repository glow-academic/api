"""Tests for search_sessions."""

from datetime import UTC, datetime, timedelta

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.sessions.create import create_session
from app.tools.entries.sessions.refresh import refresh_sessions
from app.tools.entries.sessions.search import search_sessions

pytestmark = pytest.mark.asyncio


async def test_finds_created_session(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    items = await search_sessions(conn, redis_client, profile_ids=[profile_id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_profile(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    items = await search_sessions(conn, redis_client, profile_ids=[nonexistent_id()])

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_from(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    # date_from in the future — should exclude everything
    future = datetime.now(UTC) + timedelta(days=1)
    items = await search_sessions(conn, redis_client, date_from=future)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_to(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    # date_to in the past — should exclude newly created
    past = datetime.now(UTC) - timedelta(days=1)
    items = await search_sessions(conn, redis_client, date_to=past)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_mcp(conn, redis_client, profile_id):
    r_mcp = await create_session(conn, redis_client, profile_id=profile_id, mcp=True)
    r_normal = await create_session(conn, redis_client, profile_id=profile_id, mcp=False)
    await refresh_sessions(conn)

    items = await search_sessions(conn, redis_client, mcp=True)

    ids = [item.id for item in items]
    assert r_mcp.id in ids
    assert r_normal.id not in ids


async def test_pagination_limit(conn, redis_client, profile_id):
    await create_session(conn, redis_client, profile_id=profile_id)
    await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    items = await search_sessions(
        conn,
        redis_client, profile_ids=[profile_id],
        limit=1,
    )

    assert len(items) == 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    await create_session(conn, redis_client, profile_id=profile_id)
    await refresh_sessions(conn)

    items = await search_sessions(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    result = await create_session(conn, redis_client, profile_id=profile_id)

    items = await search_sessions(
        conn,
        redis_client, profile_ids=[profile_id],
        bypass_mv=True,
    )

    ids = [item.id for item in items]
    assert result.id in ids
