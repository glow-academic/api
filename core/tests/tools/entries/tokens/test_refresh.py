"""Tests for refresh_tokens."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.tokens.create import create_token
from app.tools.entries.tokens.get import get_tokens
from app.tools.entries.tokens.refresh import refresh_tokens

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _run(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, session_id=session.id, group_id=group.id)
    return session, run


async def test_appears_after_refresh(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id


async def test_not_visible_before_refresh(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)

    items = await get_tokens(conn, [result.id], redis_client)

    assert items == []
