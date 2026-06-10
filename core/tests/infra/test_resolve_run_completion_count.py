"""run-completion counts completed AGENTS, not raw message rows.

A reasoning model emits TWO assistant rows per agent (a reasoning trace +
the final answer). run_complete_impl persists those rows WITHOUT linking
agent_ids, so resolve_run_completion's fallback count must reflect distinct
completed agents — counting raw rows double-counts each agent and would trip
``all_done`` after only ~half the agents finish.

Real DB + filesystem; deps injected (conn/redis/upload_folder as params).
"""

import pytest

from app.infra.websocket.persist_run_message import persist_run_message
from app.infra.websocket.resolve_run_completion import resolve_run_completion
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.agents.create import create_agent

pytestmark = pytest.mark.asyncio


async def _persist_reasoning_turn(conn, redis_client, run_id, session_id, tmp_path):
    """Mimic run_complete_impl: a reasoning row + an answer row, NO agent link."""
    await persist_run_message(
        conn, redis_client,
        run_id=run_id, session_id=session_id,
        role="assistant", content="thinking...",
        upload_folder=tmp_path, reasoning=True,
    )
    await persist_run_message(
        conn, redis_client,
        run_id=run_id, session_id=session_id,
        role="assistant", content="final answer",
        upload_folder=tmp_path,
    )


async def test_two_reasoning_agents_not_done_until_both_answer(
    conn, redis_client, profile_id, tmp_path
):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="persona"
    )
    agent_a = await create_agent(conn, name="agent-a", redis=redis_client)
    agent_b = await create_agent(conn, name="agent-b", redis=redis_client)
    run = await create_run(
        conn, redis_client,
        group_id=group.id, session_id=session.id,
        agent_ids=[agent_a.id, agent_b.id],
    )

    # Only the FIRST agent's reasoning turn is in (2 rows: reasoning + answer).
    await _persist_reasoning_turn(conn, redis_client, run.id, session.id, tmp_path)
    # The junction writes invalidate the messages hedge-cache row, so search
    # reads the MV — refresh it (sees this txn's uncommitted rows).
    await conn.execute("REFRESH MATERIALIZED VIEW messages_mv")

    state = await resolve_run_completion(conn, run_id=run.id, group_id=group.id)
    assert state.expected_agents == 2
    # Raw-row counting would see 2 rows >= 2 expected and wrongly report done.
    assert state.completed_agents == 1
    assert state.all_done is False

    # Second agent's reasoning turn lands (2 more rows → 4 total, 2 answers).
    await _persist_reasoning_turn(conn, redis_client, run.id, session.id, tmp_path)
    await conn.execute("REFRESH MATERIALIZED VIEW messages_mv")

    state = await resolve_run_completion(conn, run_id=run.id, group_id=group.id)
    assert state.completed_agents == 2
    assert state.all_done is True


async def test_single_reasoning_agent_completes(
    conn, redis_client, profile_id, tmp_path
):
    """The common single-agent path must still complete on one answer."""
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="persona"
    )
    agent = await create_agent(conn, name="solo-agent", redis=redis_client)
    run = await create_run(
        conn, redis_client,
        group_id=group.id, session_id=session.id,
        agent_ids=[agent.id],
    )

    await _persist_reasoning_turn(conn, redis_client, run.id, session.id, tmp_path)
    await conn.execute("REFRESH MATERIALIZED VIEW messages_mv")

    state = await resolve_run_completion(conn, run_id=run.id, group_id=group.id)
    assert state.expected_agents == 1
    assert state.completed_agents == 1
    assert state.all_done is True
