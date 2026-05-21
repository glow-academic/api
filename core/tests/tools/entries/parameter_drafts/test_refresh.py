"""Tests for refresh_parameter_drafts."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.parameter_drafts.create import create_parameter_draft
from app.tools.entries.parameter_drafts.refresh import (
    refresh_parameter_drafts,
)
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    return session, group


async def test_new_draft_appears_in_mv_after_refresh(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)
    result = await create_parameter_draft(
        conn, redis_client, session_id=session.id
    )

    row = await conn.fetchrow(
        "SELECT id FROM parameter_drafts_mv WHERE id = $1", result.id
    )
    assert row is None

    await refresh_parameter_drafts(conn)

    row = await conn.fetchrow(
        "SELECT id FROM parameter_drafts_mv WHERE id = $1", result.id
    )
    assert row is not None
    assert row["id"] == result.id
