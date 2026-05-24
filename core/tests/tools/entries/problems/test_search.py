"""Tests for search_problems."""

from datetime import UTC, datetime, timedelta

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.problems.create import create_problem
from app.tools.entries.problems.refresh import refresh_problems
from app.tools.entries.problems.search import search_problems
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _call(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    return session, call


async def test_finds_created_problem(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    result = await create_problem(
        conn, redis_client, session_id=session.id, call_id=call.id, type="bug", artifact_type="activity"
    )
    await refresh_problems(conn)

    items = await search_problems(conn, redis_client, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_session(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    await create_problem(conn, redis_client, session_id=session.id, call_id=call.id, type="bug", artifact_type="activity")
    await refresh_problems(conn)

    items = await search_problems(conn, redis_client, session_ids=[nonexistent_id()])

    assert items == []


async def test_filters_by_profile(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    result = await create_problem(
        conn,
        redis_client, session_id=session.id,
        call_id=call.id,
        type="bug",
        profile_id=profile_id, artifact_type="activity")
    await refresh_problems(conn)

    items = await search_problems(conn, redis_client, profile_ids=[profile_id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_filters_by_type(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    r_bug = await create_problem(
        conn, redis_client, session_id=session.id, call_id=call.id, type="bug", artifact_type="activity"
    )
    r_feature = await create_problem(
        conn, redis_client, session_id=session.id, call_id=call.id, type="feature", artifact_type="activity"
    )
    await refresh_problems(conn)

    items = await search_problems(conn, redis_client, type="bug")

    ids = [item.id for item in items]
    assert r_bug.id in ids
    assert r_feature.id not in ids


async def test_filters_by_date_from(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    result = await create_problem(
        conn, redis_client, session_id=session.id, call_id=call.id, type="bug", artifact_type="activity"
    )
    await refresh_problems(conn)

    future = datetime.now(UTC) + timedelta(days=1)
    items = await search_problems(conn, redis_client, date_from=future)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_date_to(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    result = await create_problem(
        conn, redis_client, session_id=session.id, call_id=call.id, type="bug", artifact_type="activity"
    )
    await refresh_problems(conn)

    past = datetime.now(UTC) - timedelta(days=1)
    items = await search_problems(conn, redis_client, date_to=past)

    ids = [item.id for item in items]
    assert result.id not in ids


async def test_filters_by_mcp(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    r_mcp = await create_problem(
        conn, redis_client, session_id=session.id, call_id=call.id, type="bug", mcp=True, artifact_type="activity")
    r_normal = await create_problem(
        conn, redis_client, session_id=session.id, call_id=call.id, type="bug", mcp=False, artifact_type="activity")
    await refresh_problems(conn)

    items = await search_problems(conn, redis_client, mcp=True)

    ids = [item.id for item in items]
    assert r_mcp.id in ids
    assert r_normal.id not in ids


async def test_pagination_limit(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    await create_problem(conn, redis_client, session_id=session.id, call_id=call.id, type="bug", artifact_type="activity")
    await create_problem(conn, redis_client, session_id=session.id, call_id=call.id, type="feature", artifact_type="activity")
    await refresh_problems(conn)

    items = await search_problems(conn, redis_client, session_ids=[session.id], limit=1)

    assert len(items) == 1


async def test_returns_all_without_filter(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    await create_problem(conn, redis_client, session_id=session.id, call_id=call.id, type="bug", artifact_type="activity")
    await refresh_problems(conn)

    items = await search_problems(conn, redis_client)

    assert len(items) >= 1


async def test_bypass_mv_finds_without_refresh(conn, redis_client, profile_id):
    session, call = await _call(conn, redis_client, profile_id)
    result = await create_problem(
        conn, redis_client, session_id=session.id, call_id=call.id, type="question", artifact_type="activity"
    )

    items = await search_problems(conn, redis_client, session_ids=[session.id], bypass_mv=True)

    ids = [item.id for item in items]
    assert result.id in ids
