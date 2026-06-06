"""Tests for create_message."""

from uuid import uuid4

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.create import create_message
from app.tools.entries.messages.get import get_message
from app.tools.entries.messages.search import search_messages
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.agents.create import create_agent

pytestmark = pytest.mark.asyncio


async def _run(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="persona"
    )
    return await create_run(
        conn, redis_client, group_id=group.id, session_id=session.id
    )


async def test_creates_message_entry(conn, redis_client, profile_id):
    run = await _run(conn, redis_client, profile_id)
    result = await create_message(conn, redis_client, run_id=run.id, role="user")

    assert result.id is not None
    assert result.created_at is not None


async def test_create_sets_all_fields(conn, redis_client, profile_id):
    """Created row carries the run link, role, and defaults."""
    run = await _run(conn, redis_client, profile_id)
    result = await create_message(
        conn, redis_client, run_id=run.id, role="assistant"
    )

    message = await get_message(conn, result.id, redis_client)

    assert message is not None
    assert message.id == result.id
    assert message.run_id == run.id
    assert message.role == "assistant"
    assert message.active is True
    assert message.mcp is False
    assert message.generated is True
    assert message.agent_ids == []


async def test_create_cache_matches_db(conn, redis_client, profile_id):
    """The cache row written on create matches the persisted DB row.

    #163-class guard: create writes a synthetic row to Redis and get serves
    it without touching the DB. A drift between the cached row and the real
    persisted row would make the cached and bypass-cache reads disagree.
    """
    run = await _run(conn, redis_client, profile_id)
    result = await create_message(
        conn, redis_client, run_id=run.id, role="assistant"
    )

    cached = await get_message(conn, result.id, redis_client)
    from_db = await get_message(conn, result.id, redis_client, bypass_cache=True)

    assert cached is not None
    assert from_db is not None
    assert cached.id == from_db.id
    assert cached.run_id == from_db.run_id
    assert cached.role == from_db.role
    assert cached.active == from_db.active
    assert cached.mcp == from_db.mcp
    assert cached.generated == from_db.generated
    assert cached.created_at == from_db.created_at


async def test_passes_mcp_flag(conn, redis_client, profile_id):
    run = await _run(conn, redis_client, profile_id)
    result = await create_message(
        conn, redis_client, run_id=run.id, role="user", mcp=True
    )

    message = await get_message(conn, result.id, redis_client)

    assert message is not None
    assert message.mcp is True


async def test_soft_create_is_inactive(conn, redis_client, profile_id):
    """soft=True yields an inactive row (active is the inverse of soft)."""
    run = await _run(conn, redis_client, profile_id)
    result = await create_message(
        conn, redis_client, run_id=run.id, role="user", soft=True
    )

    message = await get_message(conn, result.id, redis_client, bypass_cache=True)

    assert message is not None
    assert message.active is False


async def test_honors_explicit_id(conn, redis_client, profile_id):
    """An explicit id is used verbatim (idempotent-create primitive)."""
    run = await _run(conn, redis_client, profile_id)
    explicit_id = uuid4()
    result = await create_message(
        conn, redis_client, run_id=run.id, role="user", id=explicit_id
    )

    assert result.id == explicit_id
    message = await get_message(conn, explicit_id, redis_client)
    assert message is not None
    assert message.id == explicit_id


async def test_create_with_agent_links_them(conn, redis_client, profile_id):
    """agent_ids are persisted via the junction and surface with agents=True.

    Reads with bypass_cache=True to exercise the DB LEFT JOIN path; the
    default (agents=False) path hides the linked agent ids.
    """
    run = await _run(conn, redis_client, profile_id)
    agent = await create_agent(conn, name="create-msg-agent", redis=redis_client)
    result = await create_message(
        conn, redis_client, run_id=run.id, role="system", agent_ids=[agent.id]
    )

    default = await get_message(
        conn, result.id, redis_client, bypass_cache=True
    )
    assert default is not None
    assert default.agent_ids == []

    with_agents = await get_message(
        conn, result.id, redis_client, agents=True, bypass_cache=True
    )
    assert with_agents is not None
    assert with_agents.agent_ids == [agent.id]


async def test_reasoning_flag_persists(conn, redis_client, profile_id):
    """reasoning=True marks the row as a chain-of-thought trace in search."""
    run = await _run(conn, redis_client, profile_id)
    result = await create_message(
        conn, redis_client, run_id=run.id, role="assistant", reasoning=True
    )

    items, _ = await search_messages(conn, redis_client, run_ids=[run.id])

    match = next((m for m in items if m.message_id == result.id), None)
    assert match is not None
    assert match.reasoning is True


async def test_created_entry_is_searchable(conn, redis_client, profile_id):
    """A freshly created message is found by search on its run id."""
    run = await _run(conn, redis_client, profile_id)
    result = await create_message(
        conn, redis_client, run_id=run.id, role="assistant"
    )

    items, _ = await search_messages(conn, redis_client, run_ids=[run.id])

    match = next((m for m in items if m.message_id == result.id), None)
    assert match is not None
    assert match.run_id == run.id
    assert match.role == "assistant"
