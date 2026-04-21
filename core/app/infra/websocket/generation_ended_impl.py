"""Generation resolution — business logic for test_ended events.

Pure business logic with injected dependencies (``emit``, ``conn``, ``redis``).
No socket handler registration, no module-level sio, no global I/O —
importable without triggering the socket tree.

Flow:
  1. Derive run_id from test → call → run chain (DB black boxes)
  2. Call run_complete_impl directly so it re-runs with the graded eval
  3. run_complete_impl sees eval is graded → emits completion

No Redis resolution context. No duplicate emit logic. run_complete_impl
is the single completion gate — this function just re-triggers it.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any

import asyncpg

from app.infra.websocket.socket_event import EmitFn, internal_event
from app.tools.entries.calls.get import get_calls
from app.tools.entries.runs.get import get_run
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def _resolve_per_tool_call(
    conn: asyncpg.Connection,
    *,
    test_id: _uuid.UUID,
    strategy: str,
    threshold: float | None,
) -> "ResolutionOutcome | None":
    """Build per-tool-call scores from feedbacks and resolve via strategy.

    Uses only existing black-box search functions:
      1. search_test_invocation_entries_internal → invocations with agent_ids
      2. search_test_grades → grades (links invocation → grade_id)
      3. search_test_feedback_entries → feedbacks with tool_call_id + total
    """
    # 1. Invocations → agent mapping
    invocations, _ = await search_test_invocation_entries_internal(
        conn, test_ids=[test_id], bypass_mv=True,
    )
    if not invocations:
        return None

    invocation_to_agent: dict[_uuid.UUID, str] = {}
    invocation_ids: list[_uuid.UUID] = []
    for inv in invocations:
        invocation_ids.append(inv.invocation_id)
        if inv.agent_ids:
            invocation_to_agent[inv.invocation_id] = str(inv.agent_ids[0])

    # 2. Grades → grade_id to agent mapping
    grades = await search_test_grades(
        conn, invocation_ids=invocation_ids, bypass_mv=True,
    )
    if not grades:
        return None

    grade_to_agent: dict[_uuid.UUID, str] = {}
    grade_ids: list[_uuid.UUID] = []
    for g in grades:
        grade_ids.append(g.grade_id)
        agent_id = invocation_to_agent.get(g.invocation_id)
        if agent_id:
            grade_to_agent[g.grade_id] = agent_id

    # 3. Feedbacks → per tool_call_id scores
    feedbacks = await search_test_feedback_entries(
        conn, grade_ids=grade_ids, bypass_mv=True, limit=10000,
    )
    if not feedbacks:
        return None

    # Aggregate: tool_call_id → sum of totals + agent_id
    call_scores: dict[_uuid.UUID, float] = defaultdict(float)
    call_agent: dict[_uuid.UUID, str] = {}
    for fb in feedbacks:
        agent_id = grade_to_agent.get(fb.grade_id)
        if not agent_id:
            continue
        call_scores[fb.tool_call_id] += fb.total
        call_agent[fb.tool_call_id] = agent_id

    if not call_scores:
        return None

    # 4. Look up tool_id for each tool_call_id (for per-tool-type grouping)
    tool_call_ids = list(call_scores.keys())
    calls = await get_calls(conn, ids=tool_call_ids, bypass_mv=True)
    call_tool: dict[_uuid.UUID, str] = {
        c.id: str(c.tool_id) if c.tool_id else "unknown"
        for c in calls
    }

    # Build ScoredToolResult list grouped by tool_id
    scored = [
        ScoredToolResult(
            agent_id=call_agent[tcid],
            tool_name=call_tool.get(tcid, "unknown"),
            result_id=str(tcid),
            score=score,
        )
        for tcid, score in call_scores.items()
    ]

    return resolve_tool_results(scored, strategy=strategy, threshold=threshold)


async def generation_ended_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    conn: asyncpg.Connection,
    redis: Any,
) -> None:
    """Re-trigger run_complete after eval grading finishes.

    Derives run context from DB (test → call → run), then calls
    ``run_complete_impl`` directly so it can see the eval is now graded
    and emit the final completion. No top-level internal event involved.

    All I/O dependencies are injected — no globals accessed.
    """
    from app.infra.websocket.run_complete_impl import run_complete_impl
    test_id = data.get("test_id")
    sid = data.get("sid", "")
    if not test_id:
        return

    # Derive run_id and group_id from test → call → run chain (black boxes only)
    from app.tools.entries.test.get import get_tests

    tests = await get_tests(conn, [_uuid.UUID(test_id)])
    if not tests:
        logger.warning(f"Test {test_id} not found, cannot re-trigger run_complete")
        return

    test = tests[0]
    if not test.call_id:
        logger.warning(f"No call_id on test {test_id}")
        return

    calls = await get_calls(conn, [test.call_id])
    if not calls:
        logger.warning(f"Call {call_id_row} not found for test {test_id}")
        return

    run_id = calls[0].run_id
    run = await get_run(conn, run_id)
    if not run:
        logger.warning(f"Run {run_id} not found for test {test_id}")
        return

    logger.info(
        f"Eval graded for test {test_id}, re-triggering run_complete "
        f"for run {run_id} (group {run.group_id})"
    )

    # Direct call — run_complete_impl sees the eval is graded and emits
    # the final completion channel.
    await run_complete_impl(
        {
            "sid": sid,
            "run_id": str(run_id),
            "group_id": str(run.group_id),
            "session_id": str(run.session_id),
            "metadata": {
                "generation_test_id": test_id,
            },
        },
        emit=emit,
        conn=conn,
        redis=redis,
    )


async def _resolve_holistic(
    conn: asyncpg.Connection,
    redis: Any,
    *,
    test_id: str,
    run_id: str,
) -> None:
    """Original winner-takes-all resolution — highest holistic score wins."""
    winner = await resolve_generation_winner(conn, test_id=_uuid.UUID(test_id))

    if not winner:
        logger.warning(f"No winner resolved for test {test_id}")
        return

    winning_agent_id = str(winner.winning_agent_id)
    logger.info(
        f"Generation test {test_id} resolved: winner={winning_agent_id} "
        f"score={winner.winning_score}"
    )

    units = await get_all_units(redis, run_id=run_id)

    for unit_key, unit_state in units.items():
        parts = unit_key.split(":", 2)
        if len(parts) != 3:
            continue
        agent_id, target_type, target_name = parts

        try:
            if agent_id == winning_agent_id:
                await promote_unit(
                    redis,
                    run_id=run_id,
                    agent_id=agent_id,
                    target_type=target_type,
                    target_name=target_name,
                )
                if unit_state.result_id:
                    table = _table_name(target_type, target_name)
                    await activate_rows(
                        conn,
                        table=table,
                        ids=[_uuid.UUID(unit_state.result_id)],
                    )
                logger.info(
                    f"Promoted {agent_id}:{target_type}:{target_name} "
                    f"(score={winner.winning_score})"
                )
            else:
                await fail_unit(
                    redis,
                    run_id=run_id,
                    agent_id=agent_id,
                    target_type=target_type,
                    target_name=target_name,
                )
                logger.info(f"Failed {agent_id}:{target_type}:{target_name}")
        except Exception as e:
            logger.exception(
                f"Failed to resolve {agent_id}:{target_type}:{target_name}: {e}"
            )
