"""Resolve run completion state from DB — replaces Redis run tracker.

Composes existing black-box tools to determine:
  1. Are all agents done for this run?
  2. What did each agent produce (tool calls)?

No Redis state. Everything derived from DB records:
  - search_runs → expected agents (agent_ids on the run)
  - search_messages → completed agents (assistant messages)
  - search_calls → what tools were called

Each agent dispatched for a run gets its own execute_generation loop.
When each completes, it calls run_complete_impl directly, which uses
this function to check if all expected agents have completed by
looking at persisted messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg

from app.infra.globals import get_redis_client
from app.tools.entries.calls.search import search_calls
from app.tools.entries.messages.search import search_messages
from app.tools.entries.runs.search import search_runs
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class AgentCallResult:
    """What one agent produced: its tool calls."""

    agent_id: UUID
    tool_ids: list[UUID]


@dataclass(frozen=True)
class RunCompletionState:
    """Derived completion state for a run."""

    all_done: bool
    expected_agents: int
    completed_agents: int
    agent_results: list[AgentCallResult]


async def resolve_run_completion(
    conn: asyncpg.Connection,
    *,
    run_id: UUID,
    group_id: UUID,
) -> RunCompletionState:
    """Check if all agents for a run have completed, and what they produced.

    Composes existing black boxes only:
      1. search_runs(group_ids) → agent_ids on the run = expected agents
      2. search_messages(run_ids, role=assistant) → completed agents
      3. search_calls(run_ids) → tool call results

    Returns RunCompletionState with all_done flag and per-agent results.
    """
    redis = get_redis_client()
    # Step 1: Expected agents from the run record
    runs, _total = await search_runs(
        conn, redis,
        group_ids=[group_id],
        limit=1,
    )

    if not runs:
        return RunCompletionState(
            all_done=True, expected_agents=0,
            completed_agents=0, agent_results=[],
        )

    # Find the matching run
    run = next((r for r in runs if r.run_id == run_id), runs[0])
    expected_agent_ids = run.agent_ids or []
    expected_count = len(expected_agent_ids)

    if expected_count == 0:
        return RunCompletionState(
            all_done=True, expected_agents=0,
            completed_agents=0, agent_results=[],
        )

    # Step 2: Completed agents = assistant messages for this run
    messages, _msg_total = await search_messages(
        conn, redis,
        run_ids=[run_id],
        role="assistant",
        limit=100,
    )

    # Count unique agents from messages (if agent_ids populated)
    completed_agent_ids: set[UUID] = set()
    for msg in messages:
        for aid in (getattr(msg, "agent_ids", None) or []):
            if aid in expected_agent_ids:
                completed_agent_ids.add(aid)

    # Fallback: run_complete_impl persists assistant messages WITHOUT
    # linking agent_ids, so completed_agent_ids is empty on the hot path
    # and we approximate completed agents from the message rows. A
    # reasoning model emits TWO assistant rows per agent — a reasoning
    # trace (reasoning=True) followed by the final answer (reasoning=False)
    # — so counting raw rows double-counts each agent and trips all_done
    # after only ~half the agents finish. Count just the answer rows
    # (reasoning=False), which is exactly one per completed agent and also
    # leaves the common single-answer (non-reasoning) path counting 1.
    answer_messages = [m for m in messages if not getattr(m, "reasoning", False)]
    completed_count = (
        len(completed_agent_ids) if completed_agent_ids else len(answer_messages)
    )
    all_done = completed_count >= expected_count

    # Step 3: Tool calls for this run
    calls = await search_calls(
        conn,
        get_redis_client(),
        run_ids=[run_id],
        limit=200,
    )
    all_tool_ids = [c.tool_id for c in calls if c.tool_id]

    # Build per-agent results
    resolved_agents = completed_agent_ids if completed_agent_ids else set(expected_agent_ids)
    agent_results = [
        AgentCallResult(agent_id=aid, tool_ids=all_tool_ids)
        for aid in resolved_agents
    ]

    return RunCompletionState(
        all_done=all_done,
        expected_agents=expected_count,
        completed_agents=completed_count,
        agent_results=agent_results,
    )
