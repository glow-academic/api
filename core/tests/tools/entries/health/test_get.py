"""Tests for get_health."""

from datetime import UTC, datetime

import pytest

from app.tools.entries.health.create import create_health
from app.tools.entries.health.get import get_health
from app.tools.entries.health.search import search_health
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_gets_created_health_hour(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    ts = datetime(2031, 2, 3, 4, 5, tzinfo=UTC)
    await create_health(
        conn,
        redis_client, service="api",
        ok=True,
        latency_ms=11.5,
        ts=ts,
        session_id=session.id,
    )

    summary = (await search_health(conn, redis_client, service="api", bypass_mv=True))[0]
    items = await get_health(conn, [summary.date_hour], redis_client)

    assert len(items) == 1
    assert items[0].date_hour == summary.date_hour
    assert items[0].service == "api"


async def test_returns_empty_for_missing_hour(conn, redis_client):
    items = await get_health(conn, [datetime(2039, 1, 1, tzinfo=UTC)], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_health(conn, [], redis_client)

    assert items == []
