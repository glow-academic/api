"""Tests for profile_drafts create."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.profile_drafts.create import create_profile_draft
from app.tools.entries.profile_drafts.get import get_profile_drafts
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _setup(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    return session, group


async def test_create_returns_id(conn, profile_id):
    session, group = await _setup(conn, profile_id)
    result = await create_profile_draft(conn, group_id=group.id, session_id=session.id)

    assert result.id is not None


async def test_roundtrip_base_fields(conn, profile_id):
    session, group = await _setup(conn, profile_id)
    result = await create_profile_draft(
        conn, group_id=group.id, session_id=session.id, version=2
    )

    items = await get_profile_drafts(conn, [result.id])

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].group_id == group.id
    assert items[0].session_id == session.id
    assert items[0].version == 2
    assert items[0].active is True
    assert items[0].mcp is False
    assert items[0].generated is True


async def test_create_without_connections_returns_empty_lists(conn, profile_id):
    session, group = await _setup(conn, profile_id)
    result = await create_profile_draft(conn, group_id=group.id, session_id=session.id)

    items = await get_profile_drafts(conn, [result.id])

    assert items[0].profile_ids == []
    assert items[0].department_ids == []
    assert items[0].email_ids == []
    assert items[0].flag_ids == []
    assert items[0].name_ids == []
    assert items[0].request_limit_ids == []
    assert items[0].role_ids == []


async def test_create_with_connections(conn, profile_id):
    session, group = await _setup(conn, profile_id)

    name_id = await conn.fetchval("SELECT id FROM names_resource LIMIT 1")
    desc_id = await conn.fetchval("SELECT id FROM descriptions_resource LIMIT 1")
    dept_id = await conn.fetchval("SELECT id FROM departments_resource LIMIT 1")

    result = await create_profile_draft(
        conn,
        group_id=group.id,
        session_id=session.id,
        profile_ids=[profile_id],
        name_ids=[name_id],
        department_ids=[dept_id],
    )

    items = await get_profile_drafts(conn, [result.id])

    assert len(items) == 1
    assert profile_id in items[0].profile_ids
    assert name_id in items[0].name_ids
    assert dept_id in items[0].department_ids
    assert items[0].flag_ids == []


async def test_create_with_owner_profile(conn, profile_id):
    session, group = await _setup(conn, profile_id)

    result = await create_profile_draft(
        conn,
        group_id=group.id,
        session_id=session.id,
        profile_ids=[profile_id],
    )

    items = await get_profile_drafts(conn, [result.id])

    assert items[0].profile_ids == [profile_id]


async def test_create_with_multiple_connections(conn, profile_id):
    session, group = await _setup(conn, profile_id)

    name_ids = [
        r["id"] for r in await conn.fetch("SELECT id FROM names_resource LIMIT 2")
    ]

    result = await create_profile_draft(
        conn,
        group_id=group.id,
        session_id=session.id,
        name_ids=name_ids,
    )

    items = await get_profile_drafts(conn, [result.id])

    assert set(items[0].name_ids) == set(name_ids)
