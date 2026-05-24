"""Tests for get_rubric_drafts."""

import pytest
from app.tools.entries.groups.create import create_group
from app.tools.entries.rubric_drafts.create import create_rubric_draft
from app.tools.entries.rubric_drafts.get import get_rubric_drafts
from app.tools.entries.sessions.create import create_session
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    return session, group


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_rubric_drafts(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)
    created = _created(await create_rubric_draft(conn, redis_client, session_id=session.id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_rubric_drafts(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_rubric_drafts(conn, ids=[nonexistent_id()], redis=redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_rubric_drafts(conn, ids=[], redis=redis_client)

    assert items == []
