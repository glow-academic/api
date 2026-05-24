"""Tests for search_grant_consumptions."""

from datetime import UTC, datetime, timedelta

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.grant_consumptions.create import (
    create_grant_consumption,
)
from app.tools.entries.grant_consumptions.search import (
    search_grant_consumptions,
)
from app.tools.entries.grants.create import create_grant
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _grant(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    grant = await create_grant(conn, redis_client, session_id=session.id)
    return grant


async def test_finds_created(conn, redis_client, profile_id):
    grant = await _grant(conn, redis_client, profile_id)
    result = await create_grant_consumption(conn, redis_client, grant_id=grant.id)

    items = await search_grant_consumptions(conn, redis_client, grant_ids=[grant.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_grant_id(conn, redis_client, profile_id):
    grant = await _grant(conn, redis_client, profile_id)
    await create_grant_consumption(conn, redis_client, grant_id=grant.id)

    items = await search_grant_consumptions(conn, redis_client, grant_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_date_from(conn, redis_client, profile_id):
    grant = await _grant(conn, redis_client, profile_id)
    result = await create_grant_consumption(conn, redis_client, grant_id=grant.id)

    future = datetime.now(UTC) + timedelta(days=1)
    items = await search_grant_consumptions(conn, redis_client, date_from=future)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_to(conn, redis_client, profile_id):
    grant = await _grant(conn, redis_client, profile_id)
    result = await create_grant_consumption(conn, redis_client, grant_id=grant.id)

    past = datetime.now(UTC) - timedelta(days=1)
    items = await search_grant_consumptions(conn, redis_client, date_to=past)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_pagination_limit(conn, redis_client, profile_id):
    grant = await _grant(conn, redis_client, profile_id)
    await create_grant_consumption(conn, redis_client, grant_id=grant.id)
    await create_grant_consumption(conn, redis_client, grant_id=grant.id)

    items = await search_grant_consumptions(conn, redis_client, grant_ids=[grant.id], limit=1)

    assert len(items) == 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    grant = await _grant(conn, redis_client, profile_id)
    await create_grant_consumption(conn, redis_client, grant_id=grant.id)

    items = await search_grant_consumptions(conn, redis_client)

    assert len(items) >= 1
