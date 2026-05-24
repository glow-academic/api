"""Tests for create_system."""

import pytest

from app.tools.resources.agents.create import create_agent
from app.tools.resources.systems.create import create_system
from app.tools.resources.systems.get import get_systems

pytestmark = pytest.mark.asyncio


async def test_creates_new_system(conn, redis_client):
    result = await create_system(conn, "test-system", "desc", redis_client)

    assert result.name == "test-system"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_system(conn, "test-system-visible", redis=redis_client)

    items = await get_systems(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-system-visible"


async def test_two_creates_produce_different_ids(conn, redis_client):
    first = await create_system(conn, "test-system-dup", redis=redis_client)
    second = await create_system(conn, "test-system-dup", redis=redis_client)

    assert first.id != second.id


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_system(conn, "mcp-system", redis=redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True


async def test_round_trips_agent_links(conn, redis_client):
    agent = await create_agent(conn, "linked-agent", redis=redis_client)

    result = await create_system(
        conn,
        "linked-system",
        redis=redis_client,
        agent_ids=[agent.id],
    )

    items = await get_systems(conn, [result.id], redis_client, bypass_cache=True)

    assert items[0].agent_ids == [agent.id]
