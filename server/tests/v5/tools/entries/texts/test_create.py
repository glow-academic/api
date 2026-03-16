"""Tests for create_text."""

import pytest

from app.tools.entries.sessions.create import create_session
from app.tools.entries.texts.create import create_text
from app.tools.entries.texts.get import get_text

pytestmark = pytest.mark.asyncio


async def _session(conn, profile_id):
    return await create_session(conn, profile_id=profile_id)


async def test_creates_text_entry(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_text(conn, session_id=session.id)

    assert result.id is not None


async def test_text_exists_in_table(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_text(conn, session_id=session.id)

    text = await get_text(conn, result.id)

    assert text is not None
    assert text.session_id == session.id
    assert text.active is True


async def test_passes_mcp_flag(conn, profile_id):
    session = await _session(conn, profile_id)
    result = await create_text(conn, session_id=session.id, mcp=True)

    text = await get_text(conn, result.id)

    assert text is not None
    assert text.mcp is True
