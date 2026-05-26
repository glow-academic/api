"""Tests for create_call."""

import pytest

from app.tools.entries.calls.create import create_call
from app.tools.entries.calls.get import get_calls
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _run(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    return session, run


async def test_creates_call_entry(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)

    assert result.id is not None


async def test_call_exists_in_table(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)

    items = await get_calls(conn, [result.id], redis_client, bypass_mv=True)

    assert len(items) == 1
    call = items[0]
    assert call.run_id == run.id


async def test_passes_external_call_id(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_call(
        conn, redis_client, run_id=run.id, session_id=session.id, external_call_id="test_call_123"
    )

    items = await get_calls(conn, [result.id], redis_client, bypass_mv=True)

    assert len(items) == 1


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    session, run = await _run(conn, redis_client, profile_id)
    result = await create_call(conn, redis_client, run_id=run.id, session_id=session.id, mcp=True)

    items = await get_calls(conn, [result.id], redis_client, bypass_mv=True)

    assert len(items) == 1
