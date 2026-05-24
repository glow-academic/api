"""Tests for get_attempts."""

import pytest
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt.get import get_attempts
from app.tools.entries.attempt.refresh import refresh_attempt
from app.tools.entries.attempt_practice.create import create_attempt_practice
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.practice.create import create_practice
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _attempt(conn, redis_client, profile_id, **overrides):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, redis_client, group_id=group.id, session_id=session.id)
    call = await create_call(conn, redis_client, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn, redis_client)
    defaults = dict(
        session_id=session.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    defaults.update(overrides)
    result = await create_attempt(conn, redis_client, **defaults)
    return session, result


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_attempt(conn, redis_client, profile_id):
    _created(await _attempt(conn, redis_client, profile_id))
    await refresh_attempt(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_attempts(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_attempts(conn, ids=[nonexistent_id()], redis=redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_attempts(conn, ids=[], redis=redis_client)

    assert items == []
