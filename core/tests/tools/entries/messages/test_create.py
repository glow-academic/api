"""Tests for create_message."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.create import create_message
from app.tools.entries.messages.get import get_message
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _run(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    return await create_run(conn, redis_client, group_id=group.id, session_id=session.id)


async def test_creates_message_entry(conn, redis_client, profile_id):
    run = await _run(conn, redis_client, profile_id)
    result = await create_message(conn, redis_client, run_id=run.id, role="user")

    assert result.id is not None
    assert result.created_at is not None


async def test_message_exists_in_table(conn, redis_client, profile_id):
    run = await _run(conn, redis_client, profile_id)
    result = await create_message(conn, redis_client, run_id=run.id, role="assistant")

    message = await get_message(conn, result.id, redis_client)

    assert message is not None
    assert message.run_id == run.id
    assert message.role == "assistant"
    assert message.active is True


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    run = await _run(conn, redis_client, profile_id)
    result = await create_message(conn, redis_client, run_id=run.id, role="user", mcp=True)

    message = await get_message(conn, result.id, redis_client)

    assert message is not None
    assert message.mcp is True
