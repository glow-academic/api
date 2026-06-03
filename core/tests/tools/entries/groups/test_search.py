"""Tests for search_groups."""

from datetime import UTC, datetime, timedelta

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group
from app.tools.entries.groups.refresh import refresh_groups
from app.tools.entries.groups.search import search_groups
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def test_finds_created_group(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    await refresh_groups(conn)

    items = await search_groups(conn, redis_client, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_session(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    await refresh_groups(conn)

    items = await search_groups(conn, redis_client, session_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_name(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    await create_group_name(conn, redis_client, result.id, "unique-test-name", session.id)
    await refresh_groups(conn)

    items = await search_groups(conn, redis_client, name="unique-test-name")

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_date_from(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    await refresh_groups(conn)

    future = datetime.now(UTC) + timedelta(days=1)
    items = await search_groups(conn, redis_client, date_from=future)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_to(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    await refresh_groups(conn)

    past = datetime.now(UTC) - timedelta(days=1)
    items = await search_groups(conn, redis_client, date_to=past)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_mcp(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    r_mcp = await create_group(conn, redis_client, session_id=session.id, mcp=True, artifact_type="persona")
    r_normal = await create_group(conn, redis_client, session_id=session.id, mcp=False, artifact_type="persona")
    await refresh_groups(conn)

    items = await search_groups(conn, redis_client, mcp=True)

    ids = [item.id for item in items]
    assert r_mcp.id in ids
    assert r_normal.id not in ids


async def test_pagination_limit(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    await refresh_groups(conn)

    items = await search_groups(conn, redis_client, session_ids=[session.id], limit=1)

    assert len(items) == 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    await refresh_groups(conn)

    items = await search_groups(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    result = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")

    items = await search_groups(conn, redis_client, session_ids=[session.id], bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
