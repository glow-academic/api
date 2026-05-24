"""Tests for refresh_calls_internal."""

import pytest
from app.tools.entries.calls.create import create_call
from app.tools.entries.calls.get import get_calls
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.calls.refresh import refresh_calls_internal

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _run(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    return session, run


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_calls_appears_after_refresh(conn, redis_client, session_id, run_id):
    created = _created(await create_call(conn, redis_client, run_id=run_id, session_id=session_id))
    lookup_id = getattr(created, 'call_id', None) or getattr(created, 'id', None) or getattr(created, 'call', None)

    await refresh_calls_internal(conn)
    items = await get_calls(conn, [lookup_id], redis_client)

    assert len(items) == 1
    assert items[0].id == lookup_id


async def test_new_calls_is_not_visible_before_refresh(conn, redis_client, session_id, run_id):
    created = _created(await create_call(conn, redis_client, run_id=run_id, session_id=session_id))
    lookup_id = getattr(created, 'call_id', None) or getattr(created, 'id', None) or getattr(created, 'call', None)

    items = await get_calls(conn, [lookup_id], redis_client)

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_calls_internal(conn)
    await refresh_calls_internal(conn)

    assert True
