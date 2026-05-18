"""Tests for create_agent — black-box using resource + artifact tools only."""

from uuid import uuid4

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.agent.create import create_agent
from app.tools.artifacts.agent.get import get_agents
from app.tools.resources.departments.create import create_department
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.flags.create import create_flag
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _u() -> str:
    return unique_tag()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_creates_bare_artifact(conn, redis_client):
    result = await create_agent(conn)
    assert result.id is not None

    items = await get_agents(conn, [result.id])
    assert len(items) == 1
    assert items[0].generated is False
    assert items[0].mcp is False


async def test_passes_mcp_flag(conn, redis_client):
    result = await create_agent(conn, mcp=True)

    items = await get_agents(conn, [result.id])
    assert items[0].mcp is True


async def test_links_single_select_junctions(conn, redis_client):
    name = await create_name(conn, f"n-{_u()}", redis_client)
    desc = await create_description(conn, f"d-{_u()}", redis_client)

    result = await create_agent(conn, name_id=name.id, description_id=desc.id)

    items = await get_agents(conn, [result.id], names=True, descriptions=True)
    p = items[0]
    assert p.name_ids == [name.id]
    assert p.description_ids == [desc.id]


async def test_links_multi_select_junctions(conn, redis_client):
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)

    result = await create_agent(conn, department_ids=[d1.id, d2.id])

    items = await get_agents(conn, [result.id], departments=True)
    assert set(items[0].department_ids) == {d1.id, d2.id}


async def test_links_flags_with_value(conn, redis_client):
    f1 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)
    f2 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)

    result = await create_agent(conn, flag_ids=[f1.id, f2.id])

    items = await get_agents(conn, [result.id], flags=True)
    assert set(items[0].flag_ids) == {f1.id, f2.id}


async def test_explicit_id_is_used(conn, redis_client):
    explicit_id = uuid4()
    result = await create_agent(conn, id=explicit_id)
    assert result.id == explicit_id

    items = await get_agents(conn, [explicit_id])
    assert len(items) == 1


async def test_no_junctions_when_none_provided(conn, redis_client):
    result = await create_agent(conn)

    items = await get_agents(
        conn,
        [result.id],
        names=True,
        descriptions=True,
        departments=True,
        flags=True,
        models=True,
        reasoning_levels=True,
        temperature_levels=True,
        tools=True,
        voices=True,
        agents=True,
    )
    p = items[0]
    assert p.name_ids == []
    assert p.department_ids == []
    assert p.flag_ids == []
    assert p.agent_ids == []
