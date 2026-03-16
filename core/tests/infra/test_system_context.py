"""Integration tests for infra.system_context — real DB, no mocks."""

import pytest
from tests.helpers import nonexistent_id, unique_tag

from app.infra.system_context import SystemContext, resolve_system_context
from app.tools.resources.systems.create import create_system

pytestmark = pytest.mark.asyncio


class TestResolveSystemContext:
    async def test_nonexistent_system_returns_none(self, pool, redis_client):
        result = await resolve_system_context(
            pool,
            redis_client,
            system_id=nonexistent_id(),
        )

        assert result is None

    async def test_system_without_agents_returns_empty_collections(
        self, pool, redis_client
    ):
        async with pool.acquire() as conn:
            system = await create_system(
                conn,
                name="empty-system",
                description="No agents attached",
                redis=redis_client,
            )

        result = await resolve_system_context(
            pool,
            redis_client,
            system_id=system.id,
        )

        assert result is not None
        assert isinstance(result, SystemContext)
        assert result.system_id == system.id
        assert result.agents == []
        assert result.models == []
        assert result.providers == []
        assert result.tools == []
        assert result.args == []
        assert result.args_outputs == []
        assert result.prompts == []
        assert result.instructions == []
        assert result.rubrics == []

    async def test_hydrates_full_system_chain(
        self, pool, conn, redis_client, system_graph_factory
    ):
        fixture = await system_graph_factory()

        result = await resolve_system_context(
            pool,
            redis_client,
            system_id=fixture.system_id,
        )

        assert result is not None
        assert isinstance(result, SystemContext)
        assert result.system_id == fixture.system_id
        assert [agent.id for agent in result.agents] == [fixture.agent_id]
        assert [model.id for model in result.models] == [fixture.model_id]
        assert [provider.id for provider in result.providers] == [fixture.provider_id]
        assert [tool.id for tool in result.tools] == [fixture.tool_id]
        assert [arg.id for arg in result.args] == [fixture.arg_id]
        assert [item.id for item in result.args_outputs] == [fixture.arg_output_id]
        assert [prompt.id for prompt in result.prompts] == [fixture.prompt_id]
        assert [instr.id for instr in result.instructions] == [fixture.instruction_id]
        assert [rubric.id for rubric in result.rubrics] == [fixture.rubric_id]

    async def test_dedupes_shared_dependencies(self, pool, redis_client):
        from app.tools.resources.agents.create import create_agent
        from app.tools.resources.args.create import create_arg
        from app.tools.resources.args_outputs.create import create_args_output
        from app.tools.resources.instructions.create import create_instruction
        from app.tools.resources.models.create import create_model
        from app.tools.resources.prompts.create import create_prompt
        from app.tools.resources.providers.create import create_provider
        from app.tools.resources.rubrics.create import create_rubric
        from app.tools.resources.tools.create import create_tool

        tag = unique_tag()
        async with pool.acquire() as conn:
            provider = await create_provider(
                conn, name=f"provider-{tag}", description="shared", redis=redis_client
            )
            model = await create_model(
                conn,
                value=f"model-{tag}",
                provider_id=provider.id,
                redis=redis_client,
            )
            prompt = await create_prompt(
                conn,
                "Shared prompt",
                f"prompt-{tag}",
                "shared",
                redis_client,
            )
            instruction = await create_instruction(
                conn, "Shared instruction", redis_client
            )
            rubric = await create_rubric(
                conn,
                redis_client,
                name=f"rubric-{tag}",
                description="shared",
            )
            arg = await create_arg(conn, f"arg-{tag}", "text", redis_client)
            arg_output = await create_args_output(
                conn,
                arg.id,
                f"arg-output-{tag}",
                redis_client,
            )
            tool = await create_tool(
                conn,
                name=f"tool-{tag}",
                args_ids=[arg.id],
                args_output_ids=[arg_output.id],
                redis=redis_client,
            )
            agent_one = await create_agent(
                conn,
                name=f"agent-one-{tag}",
                model_id=model.id,
                prompt_id=prompt.id,
                rubric_id=rubric.id,
                tool_ids=[tool.id],
                instruction_ids=[instruction.id],
                redis=redis_client,
            )
            agent_two = await create_agent(
                conn,
                name=f"agent-two-{tag}",
                model_id=model.id,
                prompt_id=prompt.id,
                rubric_id=rubric.id,
                tool_ids=[tool.id],
                instruction_ids=[instruction.id],
                redis=redis_client,
            )
            system = await create_system(
                conn,
                name=f"system-{tag}",
                agent_ids=[agent_one.id, agent_two.id],
                redis=redis_client,
            )

        result = await resolve_system_context(pool, redis_client, system_id=system.id)

        assert result is not None
        assert {agent.id for agent in result.agents} == {agent_one.id, agent_two.id}
        assert [model.id for model in result.models] == [model.id]
        assert [provider.id for provider in result.providers] == [provider.id]
        assert [tool.id for tool in result.tools] == [tool.id]
        assert [arg.id for arg in result.args] == [arg.id]
        assert [item.id for item in result.args_outputs] == [arg_output.id]
        assert [prompt.id for prompt in result.prompts] == [prompt.id]
        assert [instr.id for instr in result.instructions] == [instruction.id]
        assert [rubric_item.id for rubric_item in result.rubrics] == [rubric.id]
