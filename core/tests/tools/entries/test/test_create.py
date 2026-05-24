"""Tests for create_test."""

import pytest

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test.get import get_tests
from app.tools.entries.test.refresh import refresh_test

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _test(conn, redis_client, profile_id, **overrides):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    defaults = dict(
        call_id=call.id,
        profiles_id=profile_id,
    )
    defaults.update(overrides)
    result = await create_test(conn, redis_client, **defaults)
    return result


async def test_returns_id(conn, redis_client, profile_id):
    result = await _test(conn, redis_client, profile_id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, redis_client, profile_id):
    result = await _test(conn, redis_client, profile_id)
    await refresh_test(conn)

    items = await get_tests(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].test_id == result.id
    assert items[0].profile_id == profile_id


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    result = await _test(conn, redis_client, profile_id, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM test_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
