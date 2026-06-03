"""Tests for refresh_problems."""

import pytest

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.problems.create import create_problem
from app.tools.entries.problems.get import get_problems
from app.tools.entries.problems.refresh import refresh_problems
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _call(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    return session, call


async def test_new_problem_appears_after_refresh(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    result = await create_problem(
        conn, redis_client, session_id=session.id, call_id=call.id, type="bug", artifact_type="activity"
    )
    await refresh_problems(conn)

    items = await get_problems(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id


async def test_new_problem_not_visible_before_refresh(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    result = await create_problem(
        conn, redis_client, session_id=session.id, call_id=call.id, type="bug", artifact_type="activity"
    )

    # bypass_cache reads the genuine problems_mv (via resolve_mv_source), which
    # create does not write to — so the new row is hidden until refresh.
    items = await get_problems(conn, [result.id], redis_client, bypass_cache=True)

    assert items == []
