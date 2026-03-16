"""Integration tests for infra.websocket.setup_generation_test."""

from uuid import UUID

import pytest

from app.infra.websocket.setup_generation_test import (
    AgentTestConfig,
    GenerationTestResult,
    setup_generation_test,
)
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.test.get import get_tests
from app.tools.entries.test.refresh import refresh_test
from app.tools.entries.test_invocation.get import get_test_invocations
from app.tools.entries.test_invocation.refresh import refresh_test_invocation
from app.tools.entries.test_invocation_runs.refresh import (
    refresh_test_invocation_runs,
)
from app.tools.entries.test_invocation_runs.search import (
    search_test_invocation_runs,
)
from app.tools.resources.agents.create import create_agent
from app.tools.resources.departments.create import create_department
from app.tools.resources.instructions.create import create_instruction
from app.tools.resources.modalities.create import create_modality
from app.tools.resources.prompts.create import create_prompt
from app.tools.resources.qualities.create import create_quality
from app.tools.resources.reasoning_levels.create import create_reasoning_level
from app.tools.resources.rubrics.create import create_rubric
from app.tools.resources.temperature_levels.create import (
    create_temperature_level,
)
from app.tools.resources.tools.create import create_tool
from app.tools.resources.voices.create import create_voice

pytestmark = pytest.mark.asyncio


async def _setup_run(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(conn, group_id=group.id, session_id=session.id)
    return run.id


async def _resource_id(conn, table: str) -> UUID:
    resource_id = await conn.fetchval(f"SELECT id FROM {table} LIMIT 1")
    assert resource_id is not None
    return resource_id


async def _ensure_agent_option_resources(conn, redis_client) -> dict[str, UUID]:
    return {
        "department_id": (
            await create_department(
                conn,
                name="generation-test-department",
                redis=redis_client,
            )
        ).id,
        "voice_id": (
            await create_voice(conn, "generation-test-voice", redis_client)
        ).id,
        "reasoning_level_id": (
            await create_reasoning_level(
                conn, "generation-test-reasoning", redis_client
            )
        ).id,
        "temperature_level_id": (
            await create_temperature_level(conn, 0.7, redis_client)
        ).id,
        "quality_id": (await create_quality(conn, "high", redis_client)).id,
        "modality_id": (await create_modality(conn, "text", redis_client)).id,
        "prompt_id": (
            await create_prompt(
                conn,
                "generation-test-system-prompt",
                "generation-test-prompt",
                "generation-test-prompt-description",
                redis_client,
            )
        ).id,
        "instruction_id": (
            await create_instruction(
                conn, "generation-test-instruction-template", redis_client
            )
        ).id,
        "tool_id": (
            await create_tool(
                conn,
                name="generation-test-tool",
                redis=redis_client,
                operation="generate",
                artifacts=["test"],
            )
        ).id,
    }


async def _create_agent_config(
    conn,
    redis_client,
    *,
    name: str,
    with_options: bool = False,
) -> AgentTestConfig:
    rubric = await create_rubric(conn, redis_client, name=f"{name}-rubric")
    agent = await create_agent(
        conn,
        name=name,
        redis=redis_client,
        rubric_id=rubric.id,
    )

    if not with_options:
        return AgentTestConfig(agent_id=agent.id, rubric_id=rubric.id)

    resources = await _ensure_agent_option_resources(conn, redis_client)

    return AgentTestConfig(
        agent_id=agent.id,
        rubric_id=rubric.id,
        department_ids=[resources["department_id"]],
        voice_ids=[resources["voice_id"]],
        reasoning_level_ids=[resources["reasoning_level_id"]],
        temperature_level_ids=[resources["temperature_level_id"]],
        quality_ids=[resources["quality_id"]],
        modality_ids=[resources["modality_id"]],
        prompt_ids=[resources["prompt_id"]],
        instruction_ids=[resources["instruction_id"]],
        tool_ids=[resources["tool_id"]],
    )


async def _refresh_generation_test_views(conn) -> None:
    await refresh_test(conn)
    await refresh_test_invocation(conn)
    await refresh_test_invocation_runs(conn)


class TestSetupGenerationTest:
    async def test_empty_agents_raises(self):
        with pytest.raises(ValueError, match="at least one agent"):
            await setup_generation_test(None, agents=[], run_id=UUID(int=1))

    async def test_single_agent_creates_test_and_invocation(
        self, conn, profile_id, redis_client
    ):
        run_id = await _setup_run(conn, profile_id)
        agent = await _create_agent_config(
            conn, redis_client, name="single-generation-agent"
        )

        result = await setup_generation_test(
            conn,
            agents=[agent],
            run_id=run_id,
            profile_id=profile_id,
        )

        await _refresh_generation_test_views(conn)

        assert isinstance(result, GenerationTestResult)
        assert set(result.invocations.keys()) == {agent.agent_id}

        tests = await get_tests(conn, [result.test_id])
        assert len(tests) == 1
        assert tests[0].test_id == result.test_id
        assert tests[0].profile_id == profile_id
        assert tests[0].num_invocations == 1
        assert tests[0].infinite_mode is False
        assert tests[0].is_dynamic is False

        invocation_id = result.invocations[agent.agent_id]
        invocations = await get_test_invocations(conn, [invocation_id])
        assert len(invocations) == 1
        assert invocations[0].test_id == result.test_id
        assert invocations[0].agent_ids == [agent.agent_id]
        assert invocations[0].rubric_id == agent.rubric_id

        invocation_runs, total_count = await search_test_invocation_runs(
            conn,
            test_invocation_ids=[invocation_id],
        )
        assert total_count == 1
        assert len(invocation_runs) == 1
        assert invocation_runs[0].test_invocation_id == invocation_id
        assert invocation_runs[0].agent_ids == [agent.agent_id]

    async def test_multiple_agents_creates_invocation_per_agent(
        self, conn, profile_id, redis_client
    ):
        run_id = await _setup_run(conn, profile_id)
        first_agent = await _create_agent_config(
            conn, redis_client, name="first-multi-agent"
        )
        second_agent = await _create_agent_config(
            conn, redis_client, name="second-multi-agent"
        )

        result = await setup_generation_test(
            conn,
            agents=[first_agent, second_agent],
            run_id=run_id,
            profile_id=profile_id,
        )

        await _refresh_generation_test_views(conn)

        assert set(result.invocations.keys()) == {
            first_agent.agent_id,
            second_agent.agent_id,
        }

        tests = await get_tests(conn, [result.test_id])
        assert len(tests) == 1
        assert tests[0].num_invocations == 2

        invocation_ids = list(result.invocations.values())
        invocations = await get_test_invocations(conn, invocation_ids)
        assert len(invocations) == 2
        assert {item.test_id for item in invocations} == {result.test_id}
        assert {item.agent_ids[0] for item in invocations} == {
            first_agent.agent_id,
            second_agent.agent_id,
        }

        invocation_runs, total_count = await search_test_invocation_runs(
            conn,
            test_invocation_ids=invocation_ids,
            limit=10,
        )
        assert total_count == 2
        assert len(invocation_runs) == 2
        assert {item.test_invocation_id for item in invocation_runs} == set(
            invocation_ids
        )

    async def test_agent_config_flows_to_invocation_and_runs(
        self, conn, profile_id, redis_client
    ):
        run_id = await _setup_run(conn, profile_id)
        agent = await _create_agent_config(
            conn,
            redis_client,
            name="configured-generation-agent",
            with_options=True,
        )

        result = await setup_generation_test(
            conn,
            agents=[agent],
            run_id=run_id,
            profile_id=profile_id,
        )

        await _refresh_generation_test_views(conn)

        invocation_id = result.invocations[agent.agent_id]
        invocations = await get_test_invocations(conn, [invocation_id])
        assert len(invocations) == 1
        assert invocations[0].department_ids == agent.department_ids
        assert invocations[0].voice_id == agent.voice_ids[0]
        assert invocations[0].reasoning_level_id == agent.reasoning_level_ids[0]
        assert invocations[0].temperature_level_id == agent.temperature_level_ids[0]
        assert invocations[0].quality_id == agent.quality_ids[0]
        assert invocations[0].modality_ids == agent.modality_ids

        invocation_runs, total_count = await search_test_invocation_runs(
            conn,
            test_invocation_ids=[invocation_id],
        )
        assert total_count == 1
        assert len(invocation_runs) == 1
        assert invocation_runs[0].prompt_ids == agent.prompt_ids
        assert invocation_runs[0].instruction_ids == agent.instruction_ids
        assert invocation_runs[0].tool_ids == agent.tool_ids
        assert invocation_runs[0].voice_ids == agent.voice_ids
        assert invocation_runs[0].quality_ids == agent.quality_ids
        assert invocation_runs[0].reasoning_level_ids == agent.reasoning_level_ids
        assert invocation_runs[0].temperature_level_ids == agent.temperature_level_ids
        assert invocation_runs[0].modality_ids == agent.modality_ids

    async def test_none_config_fields_round_trip_as_empty_lists(
        self, conn, profile_id, redis_client
    ):
        run_id = await _setup_run(conn, profile_id)
        agent = await _create_agent_config(
            conn, redis_client, name="none-config-generation-agent"
        )

        result = await setup_generation_test(
            conn,
            agents=[agent],
            run_id=run_id,
            profile_id=profile_id,
        )

        await _refresh_generation_test_views(conn)

        invocation_id = result.invocations[agent.agent_id]
        invocations = await get_test_invocations(conn, [invocation_id])
        assert len(invocations) == 1
        assert invocations[0].department_ids == []
        assert invocations[0].voice_id is None
        assert invocations[0].modality_ids == []

        invocation_runs, total_count = await search_test_invocation_runs(
            conn,
            test_invocation_ids=[invocation_id],
        )
        assert total_count == 1
        assert len(invocation_runs) == 1
        assert invocation_runs[0].prompt_ids == []
        assert invocation_runs[0].instruction_ids == []
        assert invocation_runs[0].tool_ids == []
        assert invocation_runs[0].voice_ids == []
        assert invocation_runs[0].modality_ids == []
