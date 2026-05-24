"""Tests for invocation_drafts search."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.invocation_drafts.create import create_invocation_draft
from app.tools.entries.invocation_drafts.search import (
    search_invocation_drafts,
)
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    return session, group


async def test_search_finds_created(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)
    result = await create_invocation_draft(
        conn, redis_client, session_id=session.id
    )

    items = await search_invocation_drafts(conn, redis_client, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_search_filters_by_session(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)
    result = await create_invocation_draft(
        conn, redis_client, session_id=session.id
    )

    items = await search_invocation_drafts(conn, redis_client, session_ids=[session.id])

    ids = [item.id for item in items]
    assert result.id in ids


async def test_search_returns_connections(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)

    name_id = await conn.fetchval("SELECT id FROM names_resource LIMIT 1")

    result = await create_invocation_draft(
        conn,
        redis_client, session_id=session.id,
        name_ids=[name_id],
    )

    items = await search_invocation_drafts(conn, redis_client, session_ids=[session.id])

    match = [i for i in items if i.id == result.id]
    assert len(match) == 1
    assert name_id in match[0].name_ids


async def test_search_pagination(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)
    await create_invocation_draft(conn, redis_client, session_id=session.id)
    await create_invocation_draft(conn, redis_client, session_id=session.id)

    items = await search_invocation_drafts(conn, redis_client, session_ids=[session.id], limit=1)

    assert len(items) == 1
