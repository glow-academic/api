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

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _run(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, session_id=session.id, group_id=group.id)
    return session, run


async def test_finds_created_token(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await search_tokens(conn, redis_client, run_ids=[run.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_run_id(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await search_tokens(conn, redis_client, run_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_session_id(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await search_tokens(conn, redis_client, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_session_id_no_match(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await search_tokens(conn, redis_client, session_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_date_from(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    future = datetime.now(UTC) + timedelta(days=1)
    items = await search_tokens(conn, redis_client, date_from=future)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_to(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    past = datetime.now(UTC) - timedelta(days=1)
    items = await search_tokens(conn, redis_client, date_to=past)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_mcp(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    r_mcp = await create_token(conn, redis_client, run_id=run.id, session_id=session.id, mcp=True)
    r_normal = await create_token(conn, redis_client, run_id=run.id, session_id=session.id, mcp=False)
    await refresh_tokens(conn)

    items = await search_tokens(conn, redis_client, mcp=True)

    ids = [item.id for item in items]
    assert r_mcp.id in ids
    assert r_normal.id not in ids


async def test_pagination_limit(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await search_tokens(conn, redis_client, run_ids=[run.id], limit=1)

    assert len(items) == 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await search_tokens(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)

    items = await search_tokens(conn, redis_client, run_ids=[run.id], bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
