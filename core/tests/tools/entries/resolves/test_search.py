"""Tests for search_resolves."""

from datetime import UTC, datetime, timedelta

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.problems.create import create_problem
from app.tools.entries.resolves.create import create_resolve
from app.tools.entries.resolves.refresh import refresh_resolves
from app.tools.entries.resolves.search import search_resolves
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


async def test_finds_created_resolve(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    result = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id
    )
    await refresh_resolves(conn)

    items = await search_resolves(conn, redis_client, problem_ids=[problem_id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_problem_id(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    await create_resolve(conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id)
    await refresh_resolves(conn)

    items = await search_resolves(conn, redis_client, problem_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_resolved(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    r_resolved = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=True, call_id=call.id
    )
    r_unresolved = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id
    )
    await refresh_resolves(conn)

    items = await search_resolves(conn, redis_client, resolved=True)

    ids = [item.id for item in items]
    assert r_resolved.id in ids
    assert r_unresolved.id not in ids


async def test_filters_by_mcp(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    r_mcp = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id, mcp=True
    )
    r_normal = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id, mcp=False
    )
    await refresh_resolves(conn)

    items = await search_resolves(conn, redis_client, mcp=True)

    ids = [item.id for item in items]
    assert r_mcp.id in ids
    assert r_normal.id not in ids


async def test_filters_by_date_from(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    result = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id
    )
    await refresh_resolves(conn)

    future = datetime.now(UTC) + timedelta(days=1)
    items = await search_resolves(conn, redis_client, date_from=future)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_to(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    result = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id
    )
    await refresh_resolves(conn)

    past = datetime.now(UTC) - timedelta(days=1)
    items = await search_resolves(conn, redis_client, date_to=past)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_pagination_limit(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    await create_resolve(conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id)
    await create_resolve(conn, redis_client, problem_id=problem_id, resolved=True, call_id=call.id)
    await refresh_resolves(conn)

    items = await search_resolves(conn, redis_client, problem_ids=[problem_id], limit=1)

    assert len(items) == 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    await create_resolve(conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id)
    await refresh_resolves(conn)

    items = await search_resolves(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    problem_id = await _problem(conn, redis_client, session, call)
    result = await create_resolve(
        conn, redis_client, problem_id=problem_id, resolved=False, call_id=call.id
    )

    items = await search_resolves(conn, redis_client, problem_ids=[problem_id], bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
