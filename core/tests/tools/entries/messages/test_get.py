"""Tests for get_message."""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.create import create_message
from app.tools.entries.messages.get import get_message
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.agents.create import create_agent
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _run(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="persona"
    )
    run = await create_run(
        conn, redis_client, group_id=group.id, session_id=session.id
    )
    return session, run


async def test_gets_created_message(conn, redis_client, profile_id):
    _, run = await _run(conn, redis_client, profile_id)
    created = await create_message(
        conn, redis_client, run_id=run.id, role="assistant"
    )

    message = await get_message(conn, created.id, redis_client)

    assert message is not None
    assert message.id == created.id
    assert message.run_id == run.id
    assert message.role == "assistant"
    assert message.active is True
    assert message.agent_ids == []


async def test_get_message_omits_agents_by_default(conn, redis_client, profile_id):
    _, run = await _run(conn, redis_client, profile_id)
    agent = await create_agent(conn, name="get-msg-agent", redis=redis_client)
    created = await create_message(
        conn, redis_client, run_id=run.id, role="system", agent_ids=[agent.id]
    )

    # Default (agents=False) hides the agent connections.
    default = await get_message(conn, created.id, redis_client, bypass_cache=True)
    assert default is not None
    assert default.agent_ids == []

    # agents=True surfaces the linked agent id from the DB.
    with_agents = await get_message(
        conn, created.id, redis_client, agents=True, bypass_cache=True
    )
    assert with_agents is not None
    assert with_agents.agent_ids == [agent.id]


async def test_returns_none_for_missing_id(conn, redis_client):
    message = await get_message(conn, nonexistent_id(), redis_client)

    assert message is None
