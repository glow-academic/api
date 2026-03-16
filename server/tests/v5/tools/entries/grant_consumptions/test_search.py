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

pytestmark = pytest.mark.asyncio


async def _grant(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    grant = await create_grant(conn, session_id=session.id)
    return grant


async def test_finds_created(conn, profile_id):
    grant = await _grant(conn, profile_id)
    result = await create_grant_consumption(conn, grant_id=grant.id)

    items = await search_grant_consumptions(conn, grant_ids=[grant.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_grant_id(conn, profile_id):
    grant = await _grant(conn, profile_id)
    await create_grant_consumption(conn, grant_id=grant.id)

    items = await search_grant_consumptions(conn, grant_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_date_from(conn, profile_id):
    grant = await _grant(conn, profile_id)
    result = await create_grant_consumption(conn, grant_id=grant.id)

    future = datetime.now(UTC) + timedelta(days=1)
    items = await search_grant_consumptions(conn, date_from=future)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_to(conn, profile_id):
    grant = await _grant(conn, profile_id)
    result = await create_grant_consumption(conn, grant_id=grant.id)

    past = datetime.now(UTC) - timedelta(days=1)
    items = await search_grant_consumptions(conn, date_to=past)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_pagination_limit(conn, profile_id):
    grant = await _grant(conn, profile_id)
    await create_grant_consumption(conn, grant_id=grant.id)
    await create_grant_consumption(conn, grant_id=grant.id)

    items = await search_grant_consumptions(conn, grant_ids=[grant.id], limit=1)

    assert len(items) == 1


async def test_returns_all_without_filter(conn, profile_id):
    grant = await _grant(conn, profile_id)
    await create_grant_consumption(conn, grant_id=grant.id)

    items = await search_grant_consumptions(conn)

    assert len(items) >= 1
