"""Tests for get_chat_drafts."""

import pytest
from app.tools.entries.chat_drafts.create import create_chat_draft
from app.tools.entries.chat_drafts.get import get_chat_drafts
from app.tools.entries.groups.create import create_group
from app.tools.entries.sessions.create import create_session
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id, artifact_type="persona")
    return session, group


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_chat_drafts(conn, profile_id):
    session, group = await _setup(conn, profile_id)
    created = _created(await create_chat_draft(conn, session_id=session.id))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_chat_drafts(conn, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn):
    items = await get_chat_drafts(conn, ids=[nonexistent_id()])

    assert items == []


async def test_returns_empty_for_empty_ids(conn):
    items = await get_chat_drafts(conn, ids=[])

    assert items == []
