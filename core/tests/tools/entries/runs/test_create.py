"""Tests for create_run."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.runs.get import get_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


async def _group(conn, redis_client, session_id):
    return await create_group(conn, redis_client, session_id=session_id, artifact_type="persona")


async def test_creates_run_entry(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    group = await _group(conn, redis_client, session.id)
    result = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)

    assert result.id is not None


async def test_run_exists_in_table(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    group = await _group(conn, redis_client, session.id)
    result = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)

    run = await get_run(conn, result.id, redis_client)

    assert run is not None
    assert run.group_id == group.id
    assert run.session_id == session.id


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    session = await _session(conn, redis_client, profile_id)
    group = await _group(conn, redis_client, session.id)
    result = await create_run(conn, redis_client, group_id=group.id, session_id=session.id, mcp=True)

    run = await get_run(conn, result.id, redis_client)

    assert run is not None
    assert run.mcp is True
