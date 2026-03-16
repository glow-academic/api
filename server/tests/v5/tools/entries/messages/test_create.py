"""Tests for create_message."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.create import create_message
from app.tools.entries.messages.get import get_message
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _run(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    return await create_run(conn, group_id=group.id, session_id=session.id)


async def test_creates_message_entry(conn, profile_id):
    run = await _run(conn, profile_id)
    result = await create_message(conn, run_id=run.id, role="user")

    assert result.id is not None
    assert result.created_at is not None


async def test_message_exists_in_table(conn, profile_id):
    run = await _run(conn, profile_id)
    result = await create_message(conn, run_id=run.id, role="assistant")

    message = await get_message(conn, result.id)

    assert message is not None
    assert message.run_id == run.id
    assert message.role == "assistant"
    assert message.active is True


async def test_passes_mcp_flag(conn, profile_id):
    run = await _run(conn, profile_id)
    result = await create_message(conn, run_id=run.id, role="user", mcp=True)

    message = await get_message(conn, result.id)

    assert message is not None
    assert message.mcp is True
