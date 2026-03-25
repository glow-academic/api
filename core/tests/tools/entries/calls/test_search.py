"""Tests for search_calls."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.calls.create import create_call
from app.tools.entries.calls.search import search_calls
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _refresh_mv(conn):
    """Refresh calls_mv (non-concurrently, safe inside a transaction)."""
    await conn.execute("REFRESH MATERIALIZED VIEW calls_mv")


async def _setup(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    return call, run


async def test_finds_created_entry(conn, profile_id):
    call, run = await _setup(conn, profile_id)
    await _refresh_mv(conn)

    items = await search_calls(conn, run_ids=[run.id])

    ids = [item.call_id for item in items]
    assert call.id in ids


async def test_filters_by_run_id(conn, profile_id):
    await _setup(conn, profile_id)
    await _refresh_mv(conn)

    items = await search_calls(conn, run_ids=[nonexistent_id()])

    assert items == []


async def test_pagination_limit(conn, profile_id):
    call, run = await _setup(conn, profile_id)
    await _refresh_mv(conn)

    items = await search_calls(conn, run_ids=[run.id], limit=1)

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id):
    await _setup(conn, profile_id)
    await _refresh_mv(conn)

    items = await search_calls(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    call, run = await _setup(conn, profile_id)

    items = await search_calls(conn, run_ids=[run.id], bypass_mv=True)

    ids = [item.call_id for item in items]
    assert call.id in ids
