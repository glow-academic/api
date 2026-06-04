"""Tests for get_health."""

from datetime import UTC, datetime

import pytest

from app.tools.entries.health.create import create_health
from app.tools.entries.health.get import get_health
from app.tools.entries.health.refresh import refresh_health_internal
from app.tools.entries.health.search import search_health
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def test_gets_created_health_hour(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    ts = datetime(2031, 2, 3, 4, 5, tzinfo=UTC)
    await create_health(
        conn,
        redis_client, service="redis",
        ok=True,
        latency_ms=11.5,
        ts=ts,
        session_id=session.id,
    )
    await refresh_health_internal(conn)

    # Scope the search to THIS test's own hour bucket. search_health aggregates
    # by date_hour and orders DESC over the shared health_mv; an unscoped
    # service="redis" search picks up foreign "redis" rows other tests insert
    # at later hours (e.g. test_health_stack inserts one at 2031-06-01 12:00),
    # so [0] would be a foreign hour and the assertions would flake by order.
    hour = ts.replace(minute=0, second=0, microsecond=0)
    summaries = await search_health(
        conn,
        redis_client,
        service="redis",
        date_from=hour,
        date_to=hour,
    )
    assert len(summaries) == 1
    summary = summaries[0]
    items = await get_health(conn, [summary.date_hour], redis_client)

    assert len(items) == 1
    assert items[0].date_hour == summary.date_hour
    assert items[0].service == "redis"


async def test_returns_empty_for_missing_hour(conn, redis_client):
    items = await get_health(conn, [datetime(2039, 1, 1, tzinfo=UTC)], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_health(conn, [], redis_client)

    assert items == []
