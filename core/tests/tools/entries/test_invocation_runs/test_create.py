"""Tests for create_test_invocation_runs."""

import pytest

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.entries.test_invocation_runs.create import (
    create_test_invocation_runs,
)
from app.tools.entries.test_invocation_runs.get import (
    get_test_invocation_runs,
)
from app.tools.entries.test_invocation_runs.refresh import (
    refresh_test_invocation_runs,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _test_invocation_runs(conn, redis_client, profile_id, **overrides):
    """Create full chain: session → group → run → call → test → invocation → invocation_runs."""
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    test = await create_test(conn, redis_client, call_id=call.id, profiles_id=profile_id)
    call2 = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    invocation = await create_test_invocation(conn, redis_client, test_id=test.id, call_id=call2.id)
    defaults = dict(test_invocation_id=invocation.id)
    defaults.update(overrides)
    return await create_test_invocation_runs(conn, redis_client, **defaults)


async def test_returns_id(conn, redis_client, profile_id):
    result = await _test_invocation_runs(conn, redis_client, profile_id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, redis_client, profile_id):
    result = await _test_invocation_runs(conn, redis_client, profile_id)

    await refresh_test_invocation_runs(conn)
    items = await get_test_invocation_runs(conn, [result.id], redis_client)
    assert len(items) == 1


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    result = await _test_invocation_runs(conn, redis_client, profile_id, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM test_invocation_runs_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
