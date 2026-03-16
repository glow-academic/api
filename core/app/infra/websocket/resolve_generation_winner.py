"""Resolve the winning agent from a generation test.

Called after test_ended — queries the DB for grades on all invocations,
maps each grade back to its agent via the invocation's agent_ids,
and returns the agent_id with the highest score.

Composes existing black-box functions — no inline SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg

from app.tools.entries.test_grade.search import search_test_grades
from app.tools.entries.test_invocation.search import (
    search_test_invocation_entries_internal,
)


@dataclass(frozen=True)
class GenerationWinnerResult:
    """Result of resolving the generation winner."""

    winning_agent_id: UUID
    winning_invocation_id: UUID
    winning_score: int
    all_results: list[AgentGradeResult]


@dataclass(frozen=True)
class AgentGradeResult:
    """Grade result for a single agent."""

    agent_id: UUID
    invocation_id: UUID
    score: int
    passed: bool


async def resolve_generation_winner(
    conn: asyncpg.Connection,
    *,
    test_id: UUID,
) -> GenerationWinnerResult | None:
    """Query grades for all invocations of a generation test and pick the winner.

    Steps:
      1. search_test_invocation_entries_internal(test_ids=[test_id]) → invocations with agent_ids
      2. search_test_grades(invocation_ids=...) → grades per invocation
      3. Map grades to agents, highest score wins
    """
    # 1. Get all invocations for this test (with agent_ids from MV)
    invocations, _total_count = await search_test_invocation_entries_internal(
        conn,
        test_ids=[test_id],
        bypass_mv=True,
    )

    if not invocations:
        return None

    # Build invocation_id → agent_id mapping from invocation agent_ids
    invocation_to_agent: dict[UUID, UUID] = {}
    invocation_ids: list[UUID] = []
    for inv in invocations:
        invocation_ids.append(inv.invocation_id)
        if inv.agent_ids:
            invocation_to_agent[inv.invocation_id] = inv.agent_ids[0]

    # 2. Get grades (bypass MV since grades may be fresh)
    grades = await search_test_grades(
        conn,
        invocation_ids=invocation_ids,
        bypass_mv=True,
    )

    if not grades:
        return None

    # 3. Build results and pick winner
    all_results: list[AgentGradeResult] = []
    for grade in grades:
        agent_id = invocation_to_agent.get(grade.invocation_id)
        if agent_id is None:
            continue

        all_results.append(
            AgentGradeResult(
                agent_id=agent_id,
                invocation_id=grade.invocation_id,
                score=grade.score,
                passed=grade.passed,
            )
        )

    if not all_results:
        return None

    # Highest score wins — ties broken by first graded
    winner = max(all_results, key=lambda r: r.score)

    return GenerationWinnerResult(
        winning_agent_id=winner.agent_id,
        winning_invocation_id=winner.invocation_id,
        winning_score=winner.score,
        all_results=all_results,
    )
