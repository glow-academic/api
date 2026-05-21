"""Tests for create_token."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.tokens.create import create_token
from app.tools.entries.tokens.get import get_tokens
from app.tools.entries.tokens.refresh import refresh_tokens

pytestmark = pytest.mark.asyncio


async def _run(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, session_id=session.id, group_id=group.id)
    return session, run


async def test_returns_id(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].run_id == run.id
    assert items[0].active is True
    assert items[0].mcp is False


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(conn, redis_client, run_id=run.id, session_id=session.id, mcp=True)
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].mcp is True


async def test_stores_input_tokens(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(
        conn, redis_client, run_id=run.id, session_id=session.id, input_tokens=100
    )
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].input_tokens == 100


async def test_stores_output_tokens(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(
        conn, redis_client, run_id=run.id, session_id=session.id, output_tokens=200
    )
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].output_tokens == 200


async def test_stores_cached_input_tokens(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(
        conn, redis_client, run_id=run.id, session_id=session.id, cached_input_tokens=50
    )
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].cached_input_tokens == 50


async def test_stores_session_id(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].session_id == session.id
