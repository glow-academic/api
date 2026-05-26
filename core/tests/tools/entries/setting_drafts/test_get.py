"""Tests for get_setting_drafts."""

import pytest
from app.tools.entries.groups.create import create_group
from app.tools.entries.sessions.create import create_session
from app.tools.entries.setting_drafts.create import create_setting_draft
from app.tools.entries.setting_drafts.get import get_setting_drafts
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    return session, group


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_setting_drafts(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)
    created = _created(await create_setting_draft(conn, redis_client, session_id=session.id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_setting_drafts(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_setting_drafts(conn, ids=[nonexistent_id()], redis=redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_setting_drafts(conn, ids=[], redis=redis_client)

    assert items == []
