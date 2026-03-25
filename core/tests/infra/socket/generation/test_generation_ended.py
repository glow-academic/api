"""Integration tests for generation_ended_impl."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.infra.websocket.generation_ended_impl import generation_ended_impl
from app.infra.websocket.run_tracker import (
    WorkUnit,
    get_all_units,
    init_run,
    record_unit_soft,
)
from app.infra.websocket.setup_generation_test import (
    AgentTestConfig,
    setup_generation_test,
)
from app.infra.websocket.socket_event import recording_emit
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test_grade.create import create_test_grade
from app.tools.resources.agents.create import create_agent
from app.tools.resources.names.create import create_name
from app.tools.resources.rubrics.create import create_rubric

pytestmark = pytest.mark.asyncio


async def _create_generation_run(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    return run.id, session.id, group.id


async def _create_agent_config(conn, redis_client, *, name: str) -> AgentTestConfig:
    rubric = await create_rubric(conn, redis_client, name=f"{name}-rubric")
    agent = await create_agent(
        conn,
        name=name,
        redis=redis_client,
        rubric_id=rubric.id,
    )
    return AgentTestConfig(agent_id=agent.id, rubric_id=rubric.id)


async def _create_generation_resolution(
    conn,
    redis_client,
    *,
    profile_id,
):
    run_id, session_id, group_id = await _create_generation_run(conn, profile_id)
    winner_agent = await _create_agent_config(conn, redis_client, name="winner-agent")
    loser_agent = await _create_agent_config(conn, redis_client, name="loser-agent")

    generation_test = await setup_generation_test(
        conn,
        agents=[winner_agent, loser_agent],
        run_id=run_id,
        profile_id=profile_id,
    )

    winner_invocation_id = generation_test.invocations[winner_agent.agent_id]
    loser_invocation_id = generation_test.invocations[loser_agent.agent_id]

    winner_grade_call = await create_call(conn, run_id=run_id, session_id=session_id)
    loser_grade_call = await create_call(conn, run_id=run_id, session_id=session_id)

    await create_test_grade(
        conn,
        invocation_id=winner_invocation_id,
        call_id=winner_grade_call.id,
        run_id=run_id,
        time_taken=100,
        passed=True,
        score=95,
    )
    await create_test_grade(
        conn,
        invocation_id=loser_invocation_id,
        call_id=loser_grade_call.id,
        run_id=run_id,
        time_taken=100,
        passed=True,
        score=70,
    )

    return {
        "test_id": generation_test.test_id,
        "run_id": str(run_id),
        "group_id": str(group_id),
        "winner_agent_id": str(winner_agent.agent_id),
        "loser_agent_id": str(loser_agent.agent_id),
    }


async def _create_soft_name(conn, redis_client, label: str):
    return await create_name(
        conn,
        name=f"{label}-{uuid4()}",
        redis=redis_client,
        soft=True,
    )


class TestGenerationEndedImpl:
    async def test_no_test_id_emits_nothing(self):
        emit, events = recording_emit()

        await generation_ended_impl({}, emit=emit, conn=None, redis=None)

        assert events == []

    async def test_no_winner_emits_nothing(self, conn, redis_client):
        emit, events = recording_emit()

        await generation_ended_impl(
            {"test_id": str(uuid4())},
            emit=emit,
            conn=conn,
            redis=redis_client,
        )

        assert events == []

    async def test_no_resolution_context_emits_nothing(
        self, conn, profile_id, redis_client
    ):
        emit, events = recording_emit()
        resolution = await _create_generation_resolution(
            conn,
            redis_client,
            profile_id=profile_id,
        )

        await generation_ended_impl(
            {"test_id": str(resolution["test_id"])},
            emit=emit,
            conn=conn,
            redis=redis_client,
        )

        assert events == []

    async def test_emits_generation_complete_and_activates_winner(
        self, conn, profile_id, redis_client
    ):
        emit, events = recording_emit()
        resolution = await _create_generation_resolution(
            conn,
            redis_client,
            profile_id=profile_id,
        )

        winner_name = await _create_soft_name(conn, redis_client, "winner-name")
        loser_name = await _create_soft_name(conn, redis_client, "loser-name")

        await init_run(
            redis_client,
            run_id=resolution["run_id"],
            units=[
                WorkUnit(
                    agent_id=resolution["winner_agent_id"],
                    target_type="resource",
                    target_name="names",
                ),
                WorkUnit(
                    agent_id=resolution["loser_agent_id"],
                    target_type="resource",
                    target_name="names",
                ),
            ],
            num_agents=2,
        )
        await record_unit_soft(
            redis_client,
            run_id=resolution["run_id"],
            agent_id=resolution["winner_agent_id"],
            target_type="resource",
            target_name="names",
            result_id=str(winner_name.id),
        )
        await record_unit_soft(
            redis_client,
            run_id=resolution["run_id"],
            agent_id=resolution["loser_agent_id"],
            target_type="resource",
            target_name="names",
            result_id=str(loser_name.id),
        )

        await redis_client.set(
            f"generation_resolution:{resolution['test_id']}",
            json.dumps(
                {
                    "sid": "sid-1",
                    "run_id": resolution["run_id"],
                    "artifact_type": "agent",
                    "group_id": resolution["group_id"],
                    "resource_actions": {"names": "created"},
                }
            ),
        )

        await generation_ended_impl(
            {"test_id": str(resolution["test_id"])},
            emit=emit,
            conn=conn,
            redis=redis_client,
        )

        assert len(events) == 1
        event = events[0]
        assert event.bus == "internal"
        assert event.event == "generation_channel"
        assert event.data["type"] == "complete"
        assert event.data["success"] is True
        assert event.data["artifact_type"] == "agent"
        assert event.data["run_id"] == resolution["run_id"]
        assert event.data["resource_actions"] == {"names": "created"}

        winner_active = await conn.fetchval(
            "SELECT active FROM names_resource WHERE id = $1",
            winner_name.id,
        )
        loser_active = await conn.fetchval(
            "SELECT active FROM names_resource WHERE id = $1",
            loser_name.id,
        )
        assert winner_active is True
        assert loser_active is False

        assert (
            await redis_client.get(f"generation_resolution:{resolution['test_id']}")
            is None
        )
        assert await get_all_units(redis_client, run_id=resolution["run_id"]) == {}

    async def test_malformed_unit_key_skipped(self, conn, profile_id, redis_client):
        emit, events = recording_emit()
        resolution = await _create_generation_resolution(
            conn,
            redis_client,
            profile_id=profile_id,
        )

        winner_name = await _create_soft_name(conn, redis_client, "malformed-name")

        await init_run(
            redis_client,
            run_id=resolution["run_id"],
            units=[
                WorkUnit(
                    agent_id=resolution["winner_agent_id"],
                    target_type="resource",
                    target_name="names",
                )
            ],
            num_agents=1,
        )
        await record_unit_soft(
            redis_client,
            run_id=resolution["run_id"],
            agent_id=resolution["winner_agent_id"],
            target_type="resource",
            target_name="names",
            result_id=str(winner_name.id),
        )
        await redis_client.hset(
            f"run:{resolution['run_id']}:units",
            "bad:key",
            json.dumps({"state": "soft", "result_id": None, "metadata": {}}),
        )
        await redis_client.set(
            f"generation_resolution:{resolution['test_id']}",
            json.dumps(
                {
                    "sid": "sid-1",
                    "run_id": resolution["run_id"],
                    "artifact_type": "agent",
                    "group_id": resolution["group_id"],
                    "resource_actions": {"names": "created"},
                }
            ),
        )

        await generation_ended_impl(
            {"test_id": str(resolution["test_id"])},
            emit=emit,
            conn=conn,
            redis=redis_client,
        )

        assert len(events) == 1
        assert events[0].data["type"] == "complete"
        winner_active = await conn.fetchval(
            "SELECT active FROM names_resource WHERE id = $1",
            winner_name.id,
        )
        assert winner_active is True
