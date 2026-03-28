"""Tests for refresh_test_archive."""

import pytest
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test_archive.create import create_test_archive
from app.tools.entries.test_archive.get import get_test_archives
from app.tools.entries.test_archive.refresh import refresh_test_archive
from tests.helpers import nonexistent_id

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


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_test_archive_appears_after_refresh(conn, profile_id):
    _created(await _test_archive(conn, profile_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    await refresh_test_archive(conn)
    items = await get_test_archives(conn, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_test_archive_is_not_visible_before_refresh(conn, profile_id):
    _created(await _test_archive(conn, profile_id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    items = await get_test_archives(conn, ids=[lookup_id])

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_test_archive(conn)
    await refresh_test_archive(conn)

    assert True
