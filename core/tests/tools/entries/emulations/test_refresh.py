"""Tests for refresh_emulations."""

import pytest

from app.tools.entries.emulations.create import create_emulation
from app.tools.entries.emulations.get import get_emulations
from app.tools.entries.emulations.refresh import refresh_emulations
from app.tools.entries.grants.create import create_grant
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def _grant(conn, session_id):
    result = await create_grant(conn, session_id=session_id)
    return result.id


async def test_new_emulation_appears_after_refresh(conn, profile_id):
    session = await _session(conn, profile_id)
    grant_id = await _grant(conn, session.id)
    result = await create_emulation(conn, grant_id=grant_id, session_id=session.id)
    await refresh_emulations(conn)

    items = await get_emulations(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id


async def test_new_emulation_not_visible_before_refresh(conn, profile_id):
    session = await _session(conn, profile_id)
    grant_id = await _grant(conn, session.id)
    result = await create_emulation(conn, grant_id=grant_id, session_id=session.id)

    items = await get_emulations(conn, [result.id])

    assert items == []
