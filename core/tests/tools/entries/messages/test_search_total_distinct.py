"""Regression: search_messages total_count must match the DISTINCT message
count, not the pre-DISTINCT row count fanned out by the agents LEFT JOIN.

A message linked to N agents produces N rows after
``LEFT JOIN messages_agents_connection``. ``COUNT(*) OVER()`` is evaluated
before ``SELECT DISTINCT`` collapses those rows, so the reported total
over-counts multi-agent messages — corrupting the "Showing X of Y" total.
"""

import pytest

from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.create import create_message
from app.tools.entries.messages.search import search_messages
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.agents.create import create_agent

pytestmark = pytest.mark.asyncio


async def _make_run(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="persona"
    )
    run = await create_run(
        conn, redis_client, group_id=group.id, session_id=session.id
    )
    return run


async def test_total_count_matches_distinct_message_count_multi_agent(
    conn, redis_client, profile_id
):
    """One run with exactly 2 messages, one of which links to 2 agents.

    The page should hold 2 items and total_count should be 2. Before the fix,
    the multi-agent message fans out to 2 join rows, so COUNT(*) OVER()
    reports 3 (one extra) even though DISTINCT collapses the page to 2.
    """
    run = await _make_run(conn, redis_client, profile_id)

    agent_a = await create_agent(conn, name="msg-total-agent-a", redis=redis_client)
    agent_b = await create_agent(conn, name="msg-total-agent-b", redis=redis_client)

    # Message 1: linked to two agents (the fan-out source).
    await create_message(
        conn,
        redis_client,
        run_id=run.id,
        role="assistant",
        agent_ids=[agent_a.id, agent_b.id],
    )
    # Message 2: no agents.
    await create_message(conn, redis_client, run_id=run.id, role="user")

    await conn.execute("REFRESH MATERIALIZED VIEW messages_mv")

    items, total = await search_messages(
        conn, redis_client, run_ids=[run.id], bypass_cache=True
    )

    # Exactly 2 distinct messages exist for this run.
    assert len(items) == 2
    # total must equal the distinct message count, not the fanned-out row count.
    assert total == 2, f"expected total=2, got {total} (multi-agent fan-out over-count)"

    # The agent filter (now an EXISTS subquery) must still match the
    # multi-agent message exactly once, with a correct single-item total.
    a_items, a_total = await search_messages(
        conn,
        redis_client,
        run_ids=[run.id],
        agent_ids=[agent_a.id],
        bypass_cache=True,
    )
    assert len(a_items) == 1
    assert a_total == 1, f"expected agent-filtered total=1, got {a_total}"
