"""Tests for search_tokens."""

from datetime import UTC, datetime, timedelta

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.tokens.create import create_token
from app.tools.entries.tokens.refresh import refresh_tokens
from app.tools.entries.tokens.search import search_tokens

pytestmark = pytest.mark.asyncio


async def _run(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, session_id=session.id, group_id=group.id)
    return session, run


async def test_finds_created_token(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(conn, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await search_tokens(conn, run_ids=[run.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_run_id(conn, profile_id):
    session, run = await _run(conn, profile_id)
    await create_token(conn, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await search_tokens(conn, run_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_session_id(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(conn, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await search_tokens(conn, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_session_id_no_match(conn, profile_id):
    session, run = await _run(conn, profile_id)
    await create_token(conn, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await search_tokens(conn, session_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_date_from(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(conn, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    future = datetime.now(UTC) + timedelta(days=1)
    items = await search_tokens(conn, date_from=future)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_to(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(conn, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    past = datetime.now(UTC) - timedelta(days=1)
    items = await search_tokens(conn, date_to=past)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_mcp(conn, profile_id):
    session, run = await _run(conn, profile_id)
    r_mcp = await create_token(conn, run_id=run.id, session_id=session.id, mcp=True)
    r_normal = await create_token(conn, run_id=run.id, session_id=session.id, mcp=False)
    await refresh_tokens(conn)

    items = await search_tokens(conn, mcp=True)

    ids = [item.id for item in items]
    assert r_mcp.id in ids
    assert r_normal.id not in ids


async def test_pagination_limit(conn, profile_id):
    session, run = await _run(conn, profile_id)
    await create_token(conn, run_id=run.id, session_id=session.id)
    await create_token(conn, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await search_tokens(conn, run_ids=[run.id], limit=1)

    assert len(items) == 1


async def test_returns_all_without_filter(conn, profile_id):
    session, run = await _run(conn, profile_id)
    await create_token(conn, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await search_tokens(conn)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(conn, run_id=run.id, session_id=session.id)

    items = await search_tokens(conn, run_ids=[run.id], bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
