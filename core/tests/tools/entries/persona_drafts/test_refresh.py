"""Tests for refresh_persona_drafts."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.persona_drafts.create import create_persona_draft
from app.tools.entries.persona_drafts.refresh import refresh_persona_drafts
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    return session, group


async def test_new_draft_appears_in_mv_after_refresh(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)
    result = await create_persona_draft(conn, redis_client, session_id=session.id)

    row = await conn.fetchrow(
        "SELECT id FROM persona_drafts_mv WHERE id = $1", result.id
    )
    assert row is None

    await refresh_persona_drafts(conn)

    row = await conn.fetchrow(
        "SELECT id FROM persona_drafts_mv WHERE id = $1", result.id
    )
    assert row is not None
    assert row["id"] == result.id
