"""Tests for get_attempt_archives."""

import pytest
from app.tools.entries.attempt.create import create_attempt
from app.tools.entries.attempt_archive.create import create_attempt_archive
from app.tools.entries.attempt_archive.get import get_attempt_archives
from app.tools.entries.attempt_archive.refresh import refresh_attempt_archive
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.persona.create import create_persona
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _attempt_archive(conn, profile_id, **overrides):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    persona = await create_persona(conn)
    attempt = await create_attempt(
        conn,
        call_id=call.id,
        user_persona_id=persona.id,
        profiles_id=profile_id,
    )
    defaults = dict(
        attempt_id=attempt.id,
        call_id=call.id,
        archived=True,
    )
    defaults.update(overrides)
    return await create_attempt_archive(conn, **defaults)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_attempt_archive(conn, profile_id):
    _created(await _attempt_archive(conn, profile_id))
    await refresh_attempt_archive(conn)
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_attempt_archives(conn, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn):
    items = await get_attempt_archives(conn, ids=[nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn):
    items = await get_attempt_archives(conn, ids=[])

    assert items == []
