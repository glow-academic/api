"""Tests for search_logins."""

from datetime import UTC, datetime, timedelta

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.logins.create import create_login
from app.tools.entries.logins.refresh import refresh_logins
from app.tools.entries.logins.search import search_logins
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_finds_created_login(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_login(conn, session_id=session.id)
    await refresh_logins(conn)

    items = await search_logins(conn, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_session(conn, profile_id):
    session = await _session(conn, profile_id)
    await create_login(conn, session_id=session.id)
    await refresh_logins(conn)

    items = await search_logins(conn, session_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_profile(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_login(
        conn,
        session_id=session.id,
        profile_id=profile_id,
    )
    await refresh_logins(conn)

    items = await search_logins(conn, profile_ids=[profile_id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_date_from(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_login(conn, session_id=session.id)
    await refresh_logins(conn)

    future = datetime.now(UTC) + timedelta(days=1)
    items = await search_logins(conn, date_from=future)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_to(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_login(conn, session_id=session.id)
    await refresh_logins(conn)

    past = datetime.now(UTC) - timedelta(days=1)
    items = await search_logins(conn, date_to=past)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_mcp(conn, profile_id):
    session = await _session(conn, profile_id)
    r_mcp = await create_login(conn, session_id=session.id, mcp=True)
    r_normal = await create_login(conn, session_id=session.id, mcp=False)
    await refresh_logins(conn)

    items = await search_logins(conn, mcp=True)

    ids = [item.id for item in items]
    assert r_mcp.id in ids
    assert r_normal.id not in ids


async def test_pagination_limit(conn, profile_id):
    session = await _session(conn, profile_id)
    await create_login(conn, session_id=session.id)
    await create_login(conn, session_id=session.id)
    await refresh_logins(conn)

    items = await search_logins(conn, session_ids=[session.id], limit=1)

    assert len(items) == 1


async def test_returns_all_without_filter(conn, profile_id):
    session = await _session(conn, profile_id)
    await create_login(conn, session_id=session.id)
    await refresh_logins(conn)

    items = await search_logins(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_login(conn, session_id=session.id)

    items = await search_logins(conn, session_ids=[session.id], bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
