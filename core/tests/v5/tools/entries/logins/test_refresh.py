"""Tests for refresh_logins."""

import pytest

from app.tools.entries.logins.create import create_login
from app.tools.entries.logins.get import get_logins
from app.tools.entries.logins.refresh import refresh_logins
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_new_login_appears_after_refresh(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_login(conn, session_id=session.id)
    await refresh_logins(conn)

    items = await get_logins(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id


async def test_new_login_not_visible_before_refresh(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_login(conn, session_id=session.id)

    items = await get_logins(conn, [result.id])

    assert items == []
