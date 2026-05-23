"""Tests for get_tokens."""

import pytest
from tests.helpers import nonexistent_id

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


async def test_returns_by_id(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await get_tokens(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].run_id == run.id
    assert items[0].active is True
    assert items[0].created_at is not None


async def test_returns_multiple(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    r1 = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    r2 = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)
    await refresh_tokens(conn)

    items = await get_tokens(conn, [r1.id, r2.id], redis_client)

    assert len(items) == 2
    ids = {item.id for item in items}
    assert r1.id in ids
    assert r2.id in ids


async def test_returns_empty_for_missing(conn, redis_client, profile_id):
    items = await get_tokens(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client, profile_id):
    items = await get_tokens(conn, [], redis_client)

    assert items == []


async def test_bypass_mv(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_token(conn, redis_client, run_id=run.id, session_id=session.id)

    items = await get_tokens(conn, [result.id], redis_client, bypass_mv=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].run_id == run.id
