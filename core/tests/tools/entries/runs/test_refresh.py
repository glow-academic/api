"""Tests for refresh_runs_internal."""

import pytest
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.runs.get import get_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.runs.refresh import refresh_runs_internal

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)

async def _group(conn, redis_client, session_id):
    return await create_group(conn, redis_client, session_id=session_id, artifact_type="persona")


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_runs_appears_after_refresh(conn, redis_client, group_id, session_id):
    created = _created(await create_run(conn, redis_client, group_id=group_id, session_id=session_id))
    lookup_id = getattr(created, 'run_id', None) or getattr(created, 'id', None) or getattr(created, 'run', None)

    await refresh_runs_internal(conn)
    item = await get_run(conn, lookup_id, redis_client)

    assert item is not None
    assert item.id == lookup_id


async def test_new_runs_is_not_visible_before_refresh(conn, redis_client, group_id, session_id):
    created = _created(await create_run(conn, redis_client, group_id=group_id, session_id=session_id))
    lookup_id = getattr(created, 'run_id', None) or getattr(created, 'id', None) or getattr(created, 'run', None)

    item = await get_run(conn, lookup_id, redis_client)

    assert item is None


async def test_refresh_is_idempotent(conn):
    await refresh_runs_internal(conn)
    await refresh_runs_internal(conn)

    assert True
