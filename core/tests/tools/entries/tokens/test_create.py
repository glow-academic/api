"""Tests for create_token."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.tokens.create import create_token
from app.tools.entries.tokens.get import get_tokens
from app.tools.entries.tokens.refresh import refresh_tokens

pytestmark = pytest.mark.asyncio


async def _run(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, session_id=session.id, group_id=group.id)
    return session, run


async def test_returns_id(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(conn, run_id=run.id, session_id=session.id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(conn, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].run_id == run.id
    assert items[0].active is True
    assert items[0].mcp is False


async def test_passes_mcp_flag(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(conn, run_id=run.id, session_id=session.id, mcp=True)
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id])

    assert len(items) == 1
    assert items[0].mcp is True


async def test_stores_input_tokens(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(
        conn, run_id=run.id, session_id=session.id, input_tokens=100
    )
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id])

    assert len(items) == 1
    assert items[0].input_tokens == 100


async def test_stores_output_tokens(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(
        conn, run_id=run.id, session_id=session.id, output_tokens=200
    )
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id])

    assert len(items) == 1
    assert items[0].output_tokens == 200


async def test_stores_cached_input_tokens(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(
        conn, run_id=run.id, session_id=session.id, cached_input_tokens=50
    )
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id])

    assert len(items) == 1
    assert items[0].cached_input_tokens == 50


async def test_stores_session_id(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(conn, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id])

    assert len(items) == 1
    assert items[0].session_id == session.id
