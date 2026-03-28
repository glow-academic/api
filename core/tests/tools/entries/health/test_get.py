"""Tests for get_health."""

from datetime import UTC, datetime

import pytest

from app.tools.entries.health.create import create_health
from app.tools.entries.health.get import get_health
from app.tools.entries.health.search import search_health
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def test_gets_created_health_hour(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    ts = datetime(2031, 2, 3, 4, 5, tzinfo=UTC)
    await create_health(
        conn,
        service="api",
        ok=True,
        latency_ms=11.5,
        ts=ts,
        session_id=session.id,
    )

    summary = (await search_health(conn, service="api", bypass_mv=True))[0]
    items = await get_health(conn, [summary.date_hour])

    assert len(items) == 1
    assert items[0].date_hour == summary.date_hour
    assert items[0].service == "api"


async def test_returns_empty_for_missing_hour(conn):
    items = await get_health(conn, [datetime(2039, 1, 1, tzinfo=UTC)])

    assert items == []


async def test_returns_empty_for_empty_ids(conn):
    items = await get_health(conn, [])

    assert items == []
