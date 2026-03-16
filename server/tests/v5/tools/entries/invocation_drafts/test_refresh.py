"""Tests for refresh_invocation_drafts."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.invocation_drafts.create import create_invocation_draft
from app.tools.entries.invocation_drafts.refresh import (
    refresh_invocation_drafts,
)
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    return session, group


async def test_new_draft_appears_in_mv_after_refresh(conn, profile_id):
    session, group = await _setup(conn, profile_id)
    result = await create_invocation_draft(
        conn, group_id=group.id, session_id=session.id
    )

    row = await conn.fetchrow(
        "SELECT id FROM invocation_drafts_mv WHERE id = $1", result.id
    )
    assert row is None

    await refresh_invocation_drafts(conn)

    row = await conn.fetchrow(
        "SELECT id FROM invocation_drafts_mv WHERE id = $1", result.id
    )
    assert row is not None
    assert row["id"] == result.id
