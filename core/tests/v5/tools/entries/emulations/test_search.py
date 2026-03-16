"""Tests for search_emulations."""

from datetime import UTC, datetime, timedelta

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.emulations.create import create_emulation
from app.tools.entries.emulations.refresh import refresh_emulations
from app.tools.entries.emulations.search import search_emulations
from app.tools.entries.grants.create import create_grant
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def _grant(conn, session_id):
    result = await create_grant(conn, session_id=session_id)
    return result.id


async def test_finds_created_emulation(conn, profile_id):
    session = await _session(conn, profile_id)
    grant_id = await _grant(conn, session.id)
    result = await create_emulation(conn, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    items = await search_emulations(conn, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_session(conn, profile_id):
    session = await _session(conn, profile_id)
    grant_id = await _grant(conn, session.id)
    await create_emulation(conn, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    items = await search_emulations(conn, session_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_grant(conn, profile_id):
    session = await _session(conn, profile_id)
    grant_id = await _grant(conn, session.id)
    result = await create_emulation(conn, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    items = await search_emulations(conn, grant_ids=[grant_id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_wrong_grant(conn, profile_id):
    session = await _session(conn, profile_id)
    grant_id = await _grant(conn, session.id)
    await create_emulation(conn, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    items = await search_emulations(conn, grant_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_profile(conn, profile_id):
    session = await _session(conn, profile_id)
    grant_id = await _grant(conn, session.id)
    result = await create_emulation(
        conn,
        grant_id=grant_id,
        session_id=session.id,
        profile_id=profile_id,
    )
    await refresh_emulations(conn)

    items = await search_emulations(conn, profile_ids=[profile_id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_date_from(conn, profile_id):
    session = await _session(conn, profile_id)
    grant_id = await _grant(conn, session.id)
    result = await create_emulation(conn, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    future = datetime.now(UTC) + timedelta(days=1)
    items = await search_emulations(conn, date_from=future)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_to(conn, profile_id):
    session = await _session(conn, profile_id)
    grant_id = await _grant(conn, session.id)
    result = await create_emulation(conn, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    past = datetime.now(UTC) - timedelta(days=1)
    items = await search_emulations(conn, date_to=past)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_mcp(conn, profile_id):
    session = await _session(conn, profile_id)
    grant_id = await _grant(conn, session.id)
    r_mcp = await create_emulation(
        conn, grant_id=grant_id, session_id=session.id, mcp=True
    )
    r_normal = await create_emulation(
        conn, grant_id=grant_id, session_id=session.id, mcp=False
    )
    await refresh_emulations(conn)

    items = await search_emulations(conn, mcp=True)

    ids = [item.id for item in items]
    assert r_mcp.id in ids
    assert r_normal.id not in ids


async def test_pagination_limit(conn, profile_id):
    session = await _session(conn, profile_id)
    grant_id = await _grant(conn, session.id)
    await create_emulation(conn, grant_id=grant_id, session_id=session.id)
    await create_emulation(conn, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    items = await search_emulations(conn, session_ids=[session.id], limit=1)

    assert len(items) == 1


async def test_returns_all_without_filter(conn, profile_id):
    session = await _session(conn, profile_id)
    grant_id = await _grant(conn, session.id)
    await create_emulation(conn, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    items = await search_emulations(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    session = await _session(conn, profile_id)
    grant_id = await _grant(conn, session.id)
    result = await create_emulation(conn, grant_id=grant_id, session_id=session.id)

    items = await search_emulations(conn, session_ids=[session.id], bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
