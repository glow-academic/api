"""Tests for refresh_tokens."""

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


async def test_appears_after_refresh(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(conn, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id


async def test_not_visible_before_refresh(conn, profile_id):
    session, run = await _run(conn, profile_id)
    result = await create_token(conn, run_id=run.id, session_id=session.id)

    items = await get_tokens(conn, [result.id])

    assert items == []
