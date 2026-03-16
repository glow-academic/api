"""Tests for create_grant."""

import pytest

from app.tools.entries.grants.create import create_grant
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_create_returns_id(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_grant(conn, session_id=session.id)

    assert result.id is not None


async def test_roundtrip_via_db(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_grant(conn, session_id=session.id)

    row = await conn.fetchrow("SELECT * FROM grants_entry WHERE id = $1", result.id)

    assert row is not None
    assert row["id"] == result.id
    assert row["session_id"] == session.id
    assert row["active"] is True
    assert row["mcp"] is False
    assert row["generated"] is True


async def test_default_expiry(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_grant(conn, session_id=session.id)

    row = await conn.fetchrow("SELECT * FROM grants_entry WHERE id = $1", result.id)

    assert row is not None
    assert row["expires_at"] is not None
