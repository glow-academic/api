"""Tests for delete_agents — black-box using tool functions only."""

import pytest
from tests.helpers import nonexistent_id, unique_tag

from app.tools.artifacts.agent.create import create_agent
from app.tools.artifacts.agent.delete import delete_agents
from app.tools.artifacts.agent.get import get_agents
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


async def test_hard_delete_single(conn, redis_client):
    name = await create_name(conn, f"del-{_u()}", redis_client)
    p = await create_agent(conn, name_id=name.id)
    result = await delete_agents(conn, [p.id])
    assert p.id in result.deleted_ids
    got = await get_agents(conn, [p.id], active=None)
    assert len(got) == 0


async def test_hard_delete_multiple(conn, redis_client):
    ids = []
    for _ in range(3):
        name = await create_name(conn, f"del-{_u()}", redis_client)
        p = await create_agent(conn, name_id=name.id)
        ids.append(p.id)
    result = await delete_agents(conn, ids)
    assert set(result.deleted_ids) == set(ids)
    got = await get_agents(conn, ids)
    assert len(got) == 0


async def test_hard_delete_nonexistent(conn, redis_client):
    fake_id = nonexistent_id()
    result = await delete_agents(conn, [fake_id])
    assert result.deleted_ids == []


async def test_hard_delete_empty_list(conn, redis_client):
    result = await delete_agents(conn, [])
    assert result.deleted_ids == []


async def test_soft_delete_sets_inactive(conn, redis_client):
    name = await create_name(conn, f"soft-{_u()}", redis_client)
    p = await create_agent(conn, name_id=name.id)
    result = await delete_agents(conn, [p.id], soft=True)
    assert p.id in result.deleted_ids
    got = await get_agents(conn, [p.id], active=None)
    assert len(got) == 1
    assert got[0].active is False


async def test_soft_delete_recoverable(conn, redis_client):
    name = await create_name(conn, f"recover-{_u()}", redis_client)
    p = await create_agent(conn, name_id=name.id)
    await delete_agents(conn, [p.id], soft=True)
    row = await conn.fetchrow(
        "SELECT id, active FROM agent_artifact WHERE id = $1", p.id
    )
    assert row is not None
    assert row["active"] is False


async def test_hard_delete_cascades_junctions(conn, redis_client):
    name = await create_name(conn, f"cascade-{_u()}", redis_client)
    p = await create_agent(conn, name_id=name.id)
    await delete_agents(conn, [p.id])
    row = await conn.fetchrow(
        "SELECT 1 FROM agent_names_junction WHERE agent_id = $1", p.id
    )
    assert row is None
