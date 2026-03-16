"""Integration tests for infra.websocket.resolve_generation_winner."""

from uuid import UUID

import pytest

from app.infra.websocket.resolve_generation_winner import (
    GenerationWinnerResult,
    resolve_generation_winner,
)
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.create import create_test
from app.tools.entries.test_grade.create import create_test_grade
from app.tools.entries.test_invocation.create import create_test_invocation
from app.tools.resources.agents.create import create_agent

pytestmark = pytest.mark.asyncio


async def _create_generation_test(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    call = await create_call(conn, run_id=run.id, session_id=session.id)
    test = await create_test(conn, call_id=call.id, profiles_id=profile_id)
    return test.id, run.id, session.id


async def _create_invocation_with_grade(
    conn,
    *,
    test_id: UUID,
    run_id: UUID,
    session_id: UUID,
    score: int,
    passed: bool = True,
    agent_ids: list[UUID] | None = None,
) -> tuple[UUID, UUID | None]:
    call = await create_call(conn, run_id=run_id, session_id=session_id)
    invocation = await create_test_invocation(
        conn,
        test_id=test_id,
        call_id=call.id,
        agent_ids=agent_ids,
    )
    await create_test_grade(
        conn,
        invocation_id=invocation.id,
        call_id=call.id,
        run_id=run_id,
        time_taken=120,
        passed=passed,
        score=score,
    )
    return invocation.id, agent_ids[0] if agent_ids else None


async def _create_agent_id(conn, redis_client, name: str) -> UUID:
    agent = await create_agent(conn, name=name, redis=redis_client)
    return agent.id


class TestResolveGenerationWinner:
    async def test_no_invocations_returns_none(self, conn, profile_id):
        test_id, _run_id, _session_id = await _create_generation_test(conn, profile_id)

        result = await resolve_generation_winner(conn, test_id=test_id)

        assert result is None

    async def test_no_grades_returns_none(self, conn, profile_id, redis_client):
        test_id, run_id, session_id = await _create_generation_test(conn, profile_id)
        agent_id = await _create_agent_id(conn, redis_client, "winnerless-agent")
        call = await create_call(conn, run_id=run_id, session_id=session_id)
        await create_test_invocation(
            conn,
            test_id=test_id,
            call_id=call.id,
            agent_ids=[agent_id],
        )

        result = await resolve_generation_winner(conn, test_id=test_id)

        assert result is None

    async def test_single_agent_wins_by_default(self, conn, profile_id, redis_client):
        test_id, run_id, session_id = await _create_generation_test(conn, profile_id)
        agent_id = await _create_agent_id(conn, redis_client, "single-winner")
        invocation_id, _ = await _create_invocation_with_grade(
            conn,
            test_id=test_id,
            run_id=run_id,
            session_id=session_id,
            agent_ids=[agent_id],
            score=85,
        )

        result = await resolve_generation_winner(conn, test_id=test_id)

        assert isinstance(result, GenerationWinnerResult)
        assert result.winning_agent_id == agent_id
        assert result.winning_invocation_id == invocation_id
        assert result.winning_score == 85
        assert len(result.all_results) == 1

    async def test_highest_score_wins(self, conn, profile_id, redis_client):
        test_id, run_id, session_id = await _create_generation_test(conn, profile_id)
        first_agent_id = await _create_agent_id(conn, redis_client, "first-agent")
        second_agent_id = await _create_agent_id(conn, redis_client, "second-agent")

        first_invocation_id, _ = await _create_invocation_with_grade(
            conn,
            test_id=test_id,
            run_id=run_id,
            session_id=session_id,
            agent_ids=[first_agent_id],
            score=70,
        )
        second_invocation_id, _ = await _create_invocation_with_grade(
            conn,
            test_id=test_id,
            run_id=run_id,
            session_id=session_id,
            agent_ids=[second_agent_id],
            score=95,
        )

        result = await resolve_generation_winner(conn, test_id=test_id)

        assert result is not None
        assert result.winning_agent_id == second_agent_id
        assert result.winning_invocation_id == second_invocation_id
        assert result.winning_score == 95
        assert {item.invocation_id for item in result.all_results} == {
            first_invocation_id,
            second_invocation_id,
        }

    async def test_tie_first_graded_wins(self, conn, profile_id, redis_client):
        test_id, run_id, session_id = await _create_generation_test(conn, profile_id)
        first_agent_id = await _create_agent_id(conn, redis_client, "tie-first")
        second_agent_id = await _create_agent_id(conn, redis_client, "tie-second")

        first_invocation_id, _ = await _create_invocation_with_grade(
            conn,
            test_id=test_id,
            run_id=run_id,
            session_id=session_id,
            agent_ids=[first_agent_id],
            score=80,
        )
        await _create_invocation_with_grade(
            conn,
            test_id=test_id,
            run_id=run_id,
            session_id=session_id,
            agent_ids=[second_agent_id],
            score=80,
        )

        result = await resolve_generation_winner(conn, test_id=test_id)

        assert result is not None
        assert result.winning_agent_id == first_agent_id
        assert result.winning_invocation_id == first_invocation_id
        assert result.winning_score == 80

    async def test_grade_without_agent_mapping_skipped(
        self, conn, profile_id, redis_client
    ):
        test_id, run_id, session_id = await _create_generation_test(conn, profile_id)
        mapped_agent_id = await _create_agent_id(conn, redis_client, "mapped-agent")

        mapped_invocation_id, _ = await _create_invocation_with_grade(
            conn,
            test_id=test_id,
            run_id=run_id,
            session_id=session_id,
            agent_ids=[mapped_agent_id],
            score=70,
        )
        unmapped_invocation_id, _ = await _create_invocation_with_grade(
            conn,
            test_id=test_id,
            run_id=run_id,
            session_id=session_id,
            agent_ids=None,
            score=100,
        )

        result = await resolve_generation_winner(conn, test_id=test_id)

        assert result is not None
        assert result.winning_agent_id == mapped_agent_id
        assert result.winning_invocation_id == mapped_invocation_id
        assert result.winning_score == 70
        assert {item.invocation_id for item in result.all_results} == {
            mapped_invocation_id
        }
        assert unmapped_invocation_id not in {
            item.invocation_id for item in result.all_results
        }
