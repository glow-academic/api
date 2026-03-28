"""Tests for get_run_pricing_entries_internal."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.run_pricing.create import create_run_pricing_entry_internal
from app.tools.entries.run_pricing.get import get_run_pricing_entries_internal
from app.tools.entries.run_pricing.search import search_run_pricing_entries_internal
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _run(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, session_id=session.id, group_id=group.id)
    return session, run


async def test_gets_created_run_pricing_entry(conn, profile_id):
    session, run = await _run(conn, profile_id)
    created = await create_run_pricing_entry_internal(
        conn,
        session_id=session.id,
        pricing_type="input",
        run_id=run.id,
        count=7,
    )

    items = await get_run_pricing_entries_internal(conn, [created.id], bypass_cache=True)

    assert len(items) == 1
    assert items[0]["id"] == str(created.id) or items[0]["id"] == created.id
    assert items[0]["count"] == 7


async def test_returns_empty_for_missing_ids(conn):
    items = await get_run_pricing_entries_internal(conn, [], bypass_cache=True)

    assert items == []


async def test_bypass_cache_matches_search_result(conn, profile_id):
    session, run = await _run(conn, profile_id)
    created = await create_run_pricing_entry_internal(
        conn,
        session_id=session.id,
        pricing_type="input",
        run_id=run.id,
        count=9,
    )

    search_items = await search_run_pricing_entries_internal(
        conn, run_ids=[run.id], bypass_mv=True
    )
    items = await get_run_pricing_entries_internal(conn, [created.id], bypass_cache=True)

    assert len(search_items) >= 1
    assert len(items) == 1
    assert items[0]["run_id"] == str(run.id) or items[0]["run_id"] == run.id
