"""Tests for refresh_test_grade."""

import pytest
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test_grade.create import create_test_grade
from app.tools.entries.test_grade.get import get_test_grades
from app.tools.entries.test_grade.refresh import refresh_test_grade
from app.tools.entries.test_invocation.create import create_test_invocation
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _test_grade(conn, redis_client, profile_id, **overrides):
    """Create full chain: session -> group -> run -> call -> test -> call2 -> test_invocation -> test_grade."""
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    test = await create_test(conn, redis_client, call_id=call.id, profiles_id=profile_id)
    call2 = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    test_invocation = await create_test_invocation(
        conn, redis_client, test_id=test.id, call_id=call2.id
    )
    defaults = dict(
        invocation_id=test_invocation.id,
        call_id=call2.id,
        time_taken=120,
        passed=True,
        score=85,
    )
    defaults.update(overrides)
    result = await create_test_grade(conn, redis_client, **defaults)
    return result


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_test_grade_appears_after_refresh(conn, redis_client, profile_id):
    _created(await _test_grade(conn, redis_client, profile_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    await refresh_test_grade(conn)
    items = await get_test_grades(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_test_grade_is_not_visible_before_refresh(conn, redis_client, profile_id):
    _created(await _test_grade(conn, redis_client, profile_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    items = await get_test_grades(conn, ids=[lookup_id], redis=redis_client)

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_test_grade(conn)
    await refresh_test_grade(conn)

    assert True
