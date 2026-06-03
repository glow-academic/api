"""Tests for get_test_invocation_completions."""

import pytest
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.entries.test_invocation_completion.create import (
    create_test_invocation_completion,
)
from app.tools.entries.test_invocation_completion.get import (
    get_test_invocation_completions,
)
from app.tools.entries.test_invocation_completion.refresh import (
    refresh_test_invocation_completion,
)
from app.tools.entries.test_invocation_completion.get import get_test_invocation_completions
from app.tools.entries.test_invocation_completion.refresh import refresh_test_invocation_completion
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _test_invocation_completion(conn, redis_client, profile_id, **overrides):
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
        stop=False,
        error=False,
        message="",
    )
    defaults.update(overrides)
    return await create_test_invocation_completion(conn, redis_client, **defaults)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_test_invocation_completion(conn, redis_client, profile_id):
    created = await _test_invocation_completion(conn, redis_client, profile_id)
    await refresh_test_invocation_completion(conn)
    lookup_id = created.id
    items = await get_test_invocation_completions(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_test_invocation_completions(conn, ids=[nonexistent_id()], redis=redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_test_invocation_completions(conn, ids=[], redis=redis_client)

    assert items == []
