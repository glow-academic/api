"""Tests for search_health."""

import pytest

from app.tools.entries.health.create import create_health
from app.tools.entries.health.search import search_health
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    result = await create_health(
        conn, service="websocket", ok=True, latency_ms=10.0, session_id=session.id
    )
    return result


async def test_finds_created_entry(conn, profile_id):
    await _setup(conn, profile_id)

    items = await search_health(conn, service="websocket", bypass_mv=True)

    assert len(items) >= 1
    assert all(item.service == "websocket" for item in items)


async def test_filters_by_service(conn, profile_id):
    await _setup(conn, profile_id)

    items = await search_health(conn, service="nonexistent_service", bypass_mv=True)

    assert items == []


async def test_pagination_limit(conn, profile_id):
    await _setup(conn, profile_id)

    items = await search_health(conn, service="websocket", limit=1, bypass_mv=True)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id):
    await _setup(conn, profile_id)

    items = await search_health(conn, bypass_mv=True)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    await _setup(conn, profile_id)

    items = await search_health(conn, service="websocket", bypass_mv=True)

    assert len(items) >= 1
