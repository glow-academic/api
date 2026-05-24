"""Tests for get_run."""

import pytest
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.runs.get import get_run
from app.tools.entries.sessions.create import create_session
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)

async def _group(conn, redis_client, session_id):
    return await create_group(conn, redis_client, session_id=session_id, artifact_type="persona")


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_runs(conn, redis_client, group_id, session_id):
    created = _created(await create_run(conn, redis_client, group_id=group_id, session_id=session_id))
    lookup_id = getattr(created, 'run_id', None) or getattr(created, 'id', None) or getattr(created, 'run', None)
    item = await get_run(conn, lookup_id, redis_client)

    assert item is not None
    assert item.id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    item = await get_run(conn, nonexistent_id(), redis_client)

    assert item is None


async def test_returns_created_item_after_second_lookup(conn, redis_client, group_id, session_id):
    created = _created(await create_run(conn, redis_client, group_id=group_id, session_id=session_id))
    lookup_id = getattr(created, 'run_id', None) or getattr(created, 'id', None) or getattr(created, 'run', None)
    first = await get_run(conn, lookup_id, redis_client)
    second = await get_run(conn, lookup_id, redis_client)

    assert first is not None
    assert second is not None
    assert second.id == lookup_id
