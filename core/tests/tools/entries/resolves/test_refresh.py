"""Tests for refresh_resolves."""

import pytest

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.problems.create import create_problem
from app.tools.entries.resolves.create import create_resolve
from app.tools.entries.resolves.get import get_resolves
from app.tools.entries.resolves.refresh import refresh_resolves
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _call(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    return session, call


async def _problem(conn, redis_client, session, call):
    result = await create_problem(
        conn, redis_client, session_id=session.id, call_id=call.id, type="bug", artifact_type="activity"
    )
    return result.id


async def test_appears_after_refresh(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    result = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id
    )
    await refresh_resolves(conn)

    items = await get_resolves(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id


async def test_not_visible_before_refresh(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    result = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id
    )

    items = await get_resolves(conn, [result.id], redis_client)

    assert items == []
