"""Tests for profile_drafts create."""

from uuid import UUID

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.profile_drafts.create import create_profile_draft
from app.tools.entries.profile_drafts.get import get_profile_drafts
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    return session, group


async def test_create_returns_id(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)
    result = await create_profile_draft(conn, redis_client, session_id=session.id)

    assert result.id is not None


async def test_roundtrip_base_fields(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)
    result = await create_profile_draft(
        conn, redis_client, session_id=session.id
    )

    items = await get_profile_drafts(conn, [result.id], redis_client)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].session_id == session.id
    assert items[0].active is True
    assert items[0].mcp is False
    assert items[0].generated is True


async def test_create_without_connections_returns_empty_lists(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)
    result = await create_profile_draft(conn, redis_client, session_id=session.id)

    items = await get_profile_drafts(conn, [result.id], redis_client)

    assert items[0].profile_ids == []
    assert items[0].department_ids == []
    assert items[0].email_ids == []
    assert items[0].flag_ids == []
    assert items[0].name_ids == []
    assert items[0].role_ids == []


async def test_create_with_connections(conn, redis_client, profile_id, name_id: UUID, description_id: UUID, department_id: UUID):
    session, group = await _setup(conn, redis_client, profile_id)

    result = await create_profile_draft(
        conn,
        redis_client, session_id=session.id,
        profile_ids=[profile_id],
        name_ids=[name_id],
        department_ids=[department_id],
    )

    items = await get_profile_drafts(conn, [result.id], redis_client)

    assert len(items) == 1
    assert profile_id in items[0].profile_ids
    assert name_id in items[0].name_ids
    assert department_id in items[0].department_ids
    assert items[0].flag_ids == []


async def test_create_with_owner_profile(conn, redis_client, profile_id):
    session, group = await _setup(conn, redis_client, profile_id)

    result = await create_profile_draft(
        conn,
        redis_client, session_id=session.id,
        profile_ids=[profile_id],
    )

    items = await get_profile_drafts(conn, [result.id], redis_client)

    assert items[0].profile_ids == [profile_id]


async def test_create_with_multiple_connections(conn, redis_client, profile_id):
    from app.tools.resources.names.create import create_name

    session, group = await _setup(conn, redis_client, profile_id)

    name_ids = [
        (await create_name(conn, "multi-name-1", redis_client)).id,
        (await create_name(conn, "multi-name-2", redis_client)).id,
    ]

    result = await create_profile_draft(
        conn,
        redis_client, session_id=session.id,
        name_ids=name_ids,
    )

    items = await get_profile_drafts(conn, [result.id], redis_client)

    assert set(items[0].name_ids) == set(name_ids)
