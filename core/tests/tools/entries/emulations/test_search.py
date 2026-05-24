"""Tests for search_emulations."""

from datetime import UTC, datetime, timedelta

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.emulations.create import create_emulation
from app.tools.entries.emulations.refresh import refresh_emulations
from app.tools.entries.emulations.search import search_emulations
from app.tools.entries.grants.create import create_grant
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def _grant(conn, redis_client, session_id):
    result = await create_grant(conn, redis_client, session_id=session_id)
    return result.id


async def test_finds_created_emulation(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    grant_id = await _grant(conn, redis_client, session.id)
    result = await create_emulation(conn, redis_client, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    items = await search_emulations(conn, redis_client, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_session(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    grant_id = await _grant(conn, redis_client, session.id)
    await create_emulation(conn, redis_client, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    items = await search_emulations(conn, redis_client, session_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_grant(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    grant_id = await _grant(conn, redis_client, session.id)
    result = await create_emulation(conn, redis_client, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    items = await search_emulations(conn, redis_client, grant_ids=[grant_id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_wrong_grant(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    grant_id = await _grant(conn, redis_client, session.id)
    await create_emulation(conn, redis_client, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    items = await search_emulations(conn, redis_client, grant_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_profile(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    grant_id = await _grant(conn, redis_client, session.id)
    result = await create_emulation(
        conn,
        redis_client, grant_id=grant_id,
        session_id=session.id,
        profile_id=profile_id,
    )
    await refresh_emulations(conn)

    items = await search_emulations(conn, redis_client, profile_ids=[profile_id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_date_from(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    grant_id = await _grant(conn, redis_client, session.id)
    result = await create_emulation(conn, redis_client, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    future = datetime.now(UTC) + timedelta(days=1)
    items = await search_emulations(conn, redis_client, date_from=future)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_to(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    grant_id = await _grant(conn, redis_client, session.id)
    result = await create_emulation(conn, redis_client, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    past = datetime.now(UTC) - timedelta(days=1)
    items = await search_emulations(conn, redis_client, date_to=past)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_mcp(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    grant_id = await _grant(conn, redis_client, session.id)
    r_mcp = await create_emulation(
        conn, redis_client, grant_id=grant_id, session_id=session.id, mcp=True
    )
    r_normal = await create_emulation(
        conn, redis_client, grant_id=grant_id, session_id=session.id, mcp=False
    )
    await refresh_emulations(conn)

    items = await search_emulations(conn, redis_client, mcp=True)

    ids = [item.id for item in items]
    assert r_mcp.id in ids
    assert r_normal.id not in ids


async def test_pagination_limit(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    grant_id = await _grant(conn, redis_client, session.id)
    await create_emulation(conn, redis_client, grant_id=grant_id, session_id=session.id)
    await create_emulation(conn, redis_client, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    items = await search_emulations(conn, redis_client, session_ids=[session.id], limit=1)

    assert len(items) == 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    grant_id = await _grant(conn, redis_client, session.id)
    await create_emulation(conn, redis_client, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    items = await search_emulations(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    grant_id = await _grant(conn, redis_client, session.id)
    result = await create_emulation(conn, redis_client, grant_id=grant_id, session_id=session.id)

    items = await search_emulations(conn, redis_client, session_ids=[session.id], bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
