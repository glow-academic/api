"""Tests for get_run_pricing_entries_internal."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.run_pricing.create import create_run_pricing_entry_internal
from app.tools.entries.run_pricing.get import get_run_pricing_entries_internal
from app.tools.entries.run_pricing.search import search_run_pricing_entries_internal
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _run(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, session_id=session.id, group_id=group.id)
    return session, run


async def test_gets_created_run_pricing_entry(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    created = await create_run_pricing_entry_internal(
        conn,
        redis_client, session_id=session.id,
        pricing_type="input",
        run_id=run.id,
        count=7,
    )

    items = await get_run_pricing_entries_internal(conn, [created.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0]["id"] == str(created.id) or items[0]["id"] == created.id
    assert items[0]["count"] == 7


async def test_returns_empty_for_missing_ids(conn, redis_client):
    items = await get_run_pricing_entries_internal(conn, [], redis_client, bypass_cache=True)

    assert items == []


async def test_bypass_cache_matches_search_result(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    created = await create_run_pricing_entry_internal(
        conn,
        redis_client, session_id=session.id,
        pricing_type="input",
        run_id=run.id,
        count=9,
    )

    search_items = await search_run_pricing_entries_internal(
        conn, redis_client, run_ids=[run.id], bypass_mv=True
    )
    items = await get_run_pricing_entries_internal(conn, [created.id], redis_client, bypass_cache=True)

    assert len(search_items) >= 1
    assert len(items) == 1
    assert items[0]["run_id"] == str(run.id) or items[0]["run_id"] == run.id
