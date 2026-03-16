"""Tests for create_agent."""

import pytest

from app.tools.resources.agents.create import create_agent
from app.tools.resources.agents.get import get_agents
from app.tools.resources.departments.create import create_department
from app.tools.resources.instructions.create import create_instruction
from app.tools.resources.models.create import create_model
from app.tools.resources.prompts.create import create_prompt
from app.tools.resources.rubrics.create import create_rubric
from app.tools.resources.tools.create import create_tool

pytestmark = pytest.mark.asyncio


async def test_creates_new_agent(conn, redis_client):
    result = await create_agent(conn, "test-agent", "desc", redis_client)

    assert result.name == "test-agent"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_agent(conn, "test-agent-visible", redis=redis_client)

    items = await get_agents(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-agent-visible"


async def test_two_creates_produce_different_ids(conn, redis_client):
    first = await create_agent(conn, "test-agent-dup", redis=redis_client)
    second = await create_agent(conn, "test-agent-dup", redis=redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_agent(conn, "mcp-agent", redis=redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True


async def test_round_trips_department_and_tool_links(conn, redis_client):
    department = await create_department(conn, "agent-dept", redis=redis_client)
    tool = await create_tool(conn, "agent-tool", redis=redis_client)

    result = await create_agent(
        conn,
        "linked-agent",
        redis=redis_client,
        department_ids=[department.id],
        tool_ids=[tool.id],
    )

    items = await get_agents(conn, [result.id], redis_client, bypass_cache=True)

    assert items[0].department_ids == [department.id]
    assert items[0].tool_ids == [tool.id]


async def test_round_trips_model_prompt_instruction_and_rubric_links(
    conn, redis_client
):
    model = await create_model(conn, "gpt-4-agent", redis=redis_client)
    prompt = await create_prompt(
        conn,
        "You are helpful.",
        "agent-prompt",
        "Prompt for agent",
        redis_client,
    )
    instruction = await create_instruction(
        conn,
        "Follow the rubric.",
        redis_client,
    )
    rubric = await create_rubric(
        conn,
        redis_client,
        name="agent-rubric",
        description="Rubric for agent",
    )

    result = await create_agent(
        conn,
        "linked-agent-full",
        redis=redis_client,
        model_id=model.id,
        prompt_id=prompt.id,
        instruction_ids=[instruction.id],
        rubric_id=rubric.id,
    )

    items = await get_agents(conn, [result.id], redis_client, bypass_cache=True)

    assert items[0].model_id == model.id
    assert items[0].prompt_id == prompt.id
    assert items[0].instruction_ids == [instruction.id]
    assert items[0].rubric_id == rubric.id
