"""Tests for invocation_drafts search."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.entries.groups.create import create_group
from app.tools.entries.invocation_drafts.create import create_invocation_draft
from app.tools.entries.invocation_drafts.search import (
    search_invocation_drafts,
)
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    return session, group


async def test_search_finds_created(conn, profile_id):
    session, group = await _setup(conn, profile_id)
    result = await create_invocation_draft(
        conn, group_id=group.id, session_id=session.id
    )

    items = await search_invocation_drafts(conn, group_ids=[group.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_search_filters_by_group(conn, profile_id):
    session, group = await _setup(conn, profile_id)
    await create_invocation_draft(conn, group_id=group.id, session_id=session.id)

    items = await search_invocation_drafts(conn, group_ids=[nonexistent_id()])

    assert items == []


async def test_search_filters_by_session(conn, profile_id):
    session, group = await _setup(conn, profile_id)
    result = await create_invocation_draft(
        conn, group_id=group.id, session_id=session.id
    )

    items = await search_invocation_drafts(conn, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_search_returns_connections(conn, profile_id):
    session, group = await _setup(conn, profile_id)

    name_id = await conn.fetchval("SELECT id FROM names_resource LIMIT 1")

    result = await create_invocation_draft(
        conn,
        group_id=group.id,
        session_id=session.id,
        name_ids=[name_id],
    )

    items = await search_invocation_drafts(conn, group_ids=[group.id])

    match = [i for i in items if i.id == result.id]
    assert len(match) == 1
    assert name_id in match[0].name_ids


async def test_search_pagination(conn, profile_id):
    session, group = await _setup(conn, profile_id)
    await create_invocation_draft(conn, group_id=group.id, session_id=session.id)
    await create_invocation_draft(conn, group_id=group.id, session_id=session.id)

    items = await search_invocation_drafts(conn, group_ids=[group.id], limit=1)

    assert len(items) == 1
