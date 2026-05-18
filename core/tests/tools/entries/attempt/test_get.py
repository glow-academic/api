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

pytestmark = pytest.mark.asyncio


async def _attempt(conn, profile_id, **overrides):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id, artifact_type="persona")
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn)
    defaults = dict(
        call_id=call.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    defaults.update(overrides)
    result = await create_attempt(conn, **defaults)
    return session, result


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_attempt(conn, profile_id):
    _created(await _attempt(conn, profile_id))
    await refresh_attempt(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_attempts(conn, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn):
    items = await get_attempts(conn, ids=[nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn):
    items = await get_attempts(conn, ids=[])

    assert items == []
