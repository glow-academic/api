"""Tests for create_attempt_archive."""

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


async def test_returns_id(conn, profile_id):
    result = await _attempt_archive(conn, profile_id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id):
    result = await _attempt_archive(conn, profile_id)
    await refresh_attempt_archive(conn)

    items = await get_attempt_archives(conn, [result.id])

    assert len(items) == 1


async def test_passes_mcp_flag(conn, profile_id):
    result = await _attempt_archive(conn, profile_id, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM attempt_archive_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
