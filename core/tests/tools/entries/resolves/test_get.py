"""Tests for get_resolves."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.problems.create import create_problem
from app.tools.entries.resolves.create import create_resolve
from app.tools.entries.resolves.get import get_resolves
from app.tools.entries.resolves.refresh import refresh_resolves
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


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


async def test_returns_by_id(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    result = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id
    )
    await refresh_resolves(conn)

    items = await get_resolves(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].problem_id == problem_id
    assert items[0].active is True
    assert items[0].created_at is not None


async def test_returns_multiple(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    r1 = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id
    )
    r2 = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=True, call_id=call.id
    )
    await refresh_resolves(conn)

    items = await get_resolves(conn, [r1.id, r2.id], redis_client)

    assert len(items) == 2
    ids = {item.id for item in items}
    assert r1.id in ids
    assert r2.id in ids


async def test_returns_empty_for_missing(conn, redis_client, profile_id):
    items = await get_resolves(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client, profile_id):
    items = await get_resolves(conn, [], redis_client)

    assert items == []


async def test_bypass_mv(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    result = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id
    )

    items = await get_resolves(conn, [result.id], redis_client, bypass_mv=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].problem_id == problem_id
