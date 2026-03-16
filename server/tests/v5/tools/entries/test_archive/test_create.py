"""Tests for create_test_archive."""

import pytest

from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test_archive.create import create_test_archive
from app.tools.entries.test_archive.get import get_test_archives
from app.tools.entries.test_archive.refresh import refresh_test_archive

pytestmark = pytest.mark.asyncio


async def _test_archive(conn, profile_id, **overrides):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    test = await create_test(conn, call_id=call.id, profiles_id=profile_id)
    defaults = dict(
        test_id=test.id,
        call_id=call.id,
        archived=True,
    )
    defaults.update(overrides)
    return await create_test_archive(conn, **defaults)


async def test_returns_id(conn, profile_id):
    result = await _test_archive(conn, profile_id)

    assert result.id is not None


async def test_visible_via_get_after_refresh(conn, profile_id):
    result = await _test_archive(conn, profile_id)
    await refresh_test_archive(conn)

    items = await get_test_archives(conn, [result.id])

    assert len(items) == 1


async def test_passes_mcp_flag(conn, profile_id):
    result = await _test_archive(conn, profile_id, mcp=True)

    row = await conn.fetchrow(
        "SELECT mcp FROM test_archive_entry WHERE id = $1",
        result.id,
    )
    assert row is not None
    assert row["mcp"] is True
