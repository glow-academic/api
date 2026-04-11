"""Generation resolution — business logic for test_ended events.

Pure business logic with injected dependencies (``emit``, ``conn``, ``redis``).
No socket handler registration, no module-level sio, no global I/O —
importable without triggering the socket tree.

Flow:
  1. Load resolution context from generation_resolution:{test_id} (stored by run_complete_impl)
  2. If resolution_strategy set → per-tool-call resolution via feedbacks
     Else → holistic winner-takes-all via resolve_generation_winner
  3. Get all run_tracker units → promote winners, fail losers
  4. Activate winners' dormant DB records
  5. Emit generation_complete via emit callback
  6. Cleanup Redis + run tracker
"""

from __future__ import annotations

import json
import uuid as _uuid
from collections import defaultdict
from typing import Any

import asyncpg

from app.infra.activate.activate import activate_rows
from app.infra.websocket.generation_types import GenerationCompleteData
from app.infra.websocket.resolve_generation_winner import resolve_generation_winner
from app.infra.websocket.resolve_tool_results import (
    ResolutionOutcome,
    ScoredToolResult,
    resolve_tool_results,
)
from app.infra.websocket.run_tracker import (
    cleanup_run,
    fail_unit,
    get_all_units,
    promote_unit,
)
from app.infra.websocket.socket_event import EmitFn, internal_event
from app.tools.entries.calls.get import get_calls
from app.tools.entries.test_feedback.search import search_test_feedback_entries
from app.tools.entries.test_grade.search import search_test_grades
from app.tools.entries.test_invocation.search import (
    search_test_invocation_entries_internal,
)
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


def _table_name(target_type: str, target_name: str) -> str:
    """Derive DB table from run_tracker target."""
    suffix = "resource" if target_type == "resource" else "entry"
    return f"{target_name}_{suffix}"


def parse_generation_resolution_context(
    ctx: dict[str, Any],
    data: dict[str, Any],
) -> tuple[str | None, str, str, str, dict[str, Any]]:
    """Normalize stored resolution context with request fallbacks."""
    run_id = ctx.get("run_id")
    sid = ctx.get("sid", data.get("sid", ""))
    artifact_type = ctx.get("artifact_type", "unknown")
    group_id_str = ctx.get("group_id", "")
    resource_actions = ctx.get("resource_actions", {})
    return run_id, sid, artifact_type, group_id_str, resource_actions


def build_generation_complete_payload(
    *,
    sid: str,
    artifact_type: str,
    group_id: str,
    run_id: str,
    resource_actions: dict[str, Any],
) -> dict[str, Any]:
    """Build the final generation completion payload."""
    return GenerationCompleteData(
        sid=sid,
        artifact_type=artifact_type,
        group_id=group_id,
        run_id=run_id,
        success=True,
        message=f"{artifact_type.capitalize()} generation resolved",
        resource_actions=resource_actions,
    ).model_dump(mode="json")


async def _resolve_per_tool_call(
    conn: asyncpg.Connection,
    *,
    test_id: _uuid.UUID,
    strategy: str,
    threshold: float | None,
) -> ResolutionOutcome | None:
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
    """Resolve contested targets after test grading completes.

    All I/O dependencies are injected — no globals accessed.
    Callable from socket handler, API, or tests.
    """
    test_id = data.get("test_id")
    if not test_id:
        return

    # Step 1: Load resolution context (keyed by test_id, stored by run_complete_impl)
    ctx: dict[str, Any] = {}
    try:
        ctx_raw = await redis.get(f"generation_resolution:{test_id}")
        if ctx_raw:
            ctx = json.loads(ctx_raw)
    except Exception as e:
        logger.warning(f"Failed to load resolution context for test {test_id}: {e}")

    run_id, sid, artifact_type, group_id_str, resource_actions = (
        parse_generation_resolution_context(ctx, data)
    )
    if not run_id:
        logger.warning(f"No run_id in resolution context for test {test_id}")
        return

    resolution_strategy = ctx.get("resolution_strategy")
    resolution_threshold = ctx.get("resolution_threshold")

    # Step 2: Resolve — per-tool-call or holistic
    if resolution_strategy:
        # Per-tool-call resolution via feedbacks
        outcome = await _resolve_per_tool_call(
            conn,
            test_id=_uuid.UUID(test_id),
            strategy=resolution_strategy,
            threshold=resolution_threshold,
        )

        if outcome:
            promote_ids = set(outcome.promote)
            fail_ids = set(outcome.fail)

            units = await get_all_units(redis, run_id=run_id)

            for unit_key, unit_state in units.items():
                parts = unit_key.split(":", 2)
                if len(parts) != 3:
                    continue
                agent_id, target_type, target_name = parts

                result_id = unit_state.result_id
                try:
                    if result_id and result_id in promote_ids:
                        await promote_unit(
                            redis,
                            run_id=run_id,
                            agent_id=agent_id,
                            target_type=target_type,
                            target_name=target_name,
                        )
                        table = _table_name(target_type, target_name)
                        await activate_rows(
                            conn,
                            table=table,
                            ids=[_uuid.UUID(result_id)],
                        )
                        logger.info(
                            f"Promoted {agent_id}:{target_type}:{target_name} "
                            f"(per-tool-call, strategy={resolution_strategy})"
                        )
                    elif result_id and result_id in fail_ids:
                        await fail_unit(
                            redis,
                            run_id=run_id,
                            agent_id=agent_id,
                            target_type=target_type,
                            target_name=target_name,
                        )
                        logger.info(
                            f"Failed {agent_id}:{target_type}:{target_name} "
                            f"(per-tool-call)"
                        )
                    else:
                        # Not in feedback results — auto-promote (uncontested)
                        await promote_unit(
                            redis,
                            run_id=run_id,
                            agent_id=agent_id,
                            target_type=target_type,
                            target_name=target_name,
                        )
                        if result_id:
                            table = _table_name(target_type, target_name)
                            await activate_rows(
                                conn,
                                table=table,
                                ids=[_uuid.UUID(result_id)],
                            )
                except Exception as e:
                    logger.exception(
                        f"Failed to resolve {agent_id}:{target_type}:{target_name}: {e}"
                    )
        else:
            logger.warning(
                f"Per-tool-call resolution returned no outcome for test {test_id}, "
                f"falling back to holistic"
            )
            await _resolve_holistic(
                conn, redis,
                test_id=test_id, run_id=run_id,
            )
    else:
        # Holistic winner-takes-all (existing behavior)
        await _resolve_holistic(
            conn, redis,
            test_id=test_id, run_id=run_id,
        )

    # Step 3: Emit generation_complete
    await emit(
        [
            internal_event(
                "generation_channel",
                build_generation_complete_payload(
                    sid=sid,
                    artifact_type=artifact_type,
                    group_id=group_id_str,
                    run_id=run_id,
                    resource_actions=resource_actions,
                ),
            )
        ]
    )

    # Step 4: Cleanup
    await cleanup_run(redis, run_id=run_id)
    try:
        await redis.delete(f"generation_resolution:{test_id}")
    except Exception:
        pass


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
