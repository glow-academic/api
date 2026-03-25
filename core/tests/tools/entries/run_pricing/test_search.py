"""Tests for search_run_pricing_entries_internal."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.groups.create import create_group
from app.tools.entries.run_pricing.search import (
    search_run_pricing_entries_internal,
)
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _pricing_type(conn):
    return await conn.fetchval("SELECT unnest(enum_range(NULL::pricing_type)) LIMIT 1")


async def _setup(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, session_id=session.id, group_id=group.id)
    pricing_type = await _pricing_type(conn)

    entry_id = await conn.fetchval(
        "INSERT INTO run_pricing_entry (pricing_type, count, run_id, session_id) "
        "VALUES ($1::pricing_type, $2, $3, $4) RETURNING id",
        pricing_type,
        5,
        run.id,
        session.id,
    )
    return entry_id, run


async def test_finds_created_entry(conn, profile_id):
    entry_id, run = await _setup(conn, profile_id)

    items = await search_run_pricing_entries_internal(
        conn, run_ids=[run.id], bypass_mv=True
    )

    ids = [item.id for item in items]
    assert entry_id in ids


async def test_filters_by_run_id(conn, profile_id):
    await _setup(conn, profile_id)

    items = await search_run_pricing_entries_internal(
        conn, run_ids=[nonexistent_id()], bypass_mv=True
    )

    assert items == []


async def test_pagination_limit(conn, profile_id):
    entry_id, run = await _setup(conn, profile_id)

    items = await search_run_pricing_entries_internal(
        conn, run_ids=[run.id], limit=1, bypass_mv=True
    )

    assert len(items) <= 1


async def test_returns_all_without_filter(conn, profile_id):
    await _setup(conn, profile_id)

    items = await search_run_pricing_entries_internal(conn, bypass_mv=True)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    entry_id, run = await _setup(conn, profile_id)

    items = await search_run_pricing_entries_internal(
        conn, run_ids=[run.id], bypass_mv=True
    )

    ids = [item.id for item in items]
    assert entry_id in ids
