"""Tests for search_agents — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.agent.create import create_agent
from app.tools.artifacts.agent.search import search_agents
from app.tools.resources.departments.create import create_department
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


async def test_bare_search_returns_results(conn, redis_client):
    name = await create_name(conn, f"bare-{_u()}", redis_client)
    a = await create_agent(conn, name_id=name.id)
    ids, _total = await search_agents(conn)
    assert a.id in ids


async def test_text_search_filters_by_name(conn, redis_client):
    tag = _u()
    name_match = await create_name(conn, f"match-{tag}", redis_client)
    name_other = await create_name(conn, f"other-{_u()}", redis_client)
    a1 = await create_agent(conn, name_id=name_match.id)
    a2 = await create_agent(conn, name_id=name_other.id)
    ids, _total = await search_agents(conn, search=f"match-{tag}")
    assert a1.id in ids
    assert a2.id not in ids


async def test_text_search_filters_by_description(conn, redis_client):
    tag = _u()
    desc = await create_description(conn, f"desc-{tag}", redis_client)
    a1 = await create_agent(conn, description_id=desc.id)
    a2 = await create_agent(conn)
    ids, _total = await search_agents(conn, search=f"desc-{tag}")
    assert a1.id in ids
    assert a2.id not in ids


async def test_department_filter(conn, redis_client):
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)
    a1 = await create_agent(conn, department_ids=[d1.id])
    a2 = await create_agent(conn, department_ids=[d2.id])
    ids, _total = await search_agents(conn, department_ids=[d1.id])
    assert a1.id in ids
    assert a2.id not in ids


async def test_model_ids_filter(conn, redis_client):
    m1 = await conn.fetchval(
        "INSERT INTO models_resource (name, value) VALUES ($1, $1) RETURNING id",
        f"m-{_u()}",
    )
    m2 = await conn.fetchval(
        "INSERT INTO models_resource (name, value) VALUES ($1, $1) RETURNING id",
        f"m-{_u()}",
    )
    a1 = await create_agent(conn, model_ids=[m1])
    a2 = await create_agent(conn, model_ids=[m2])
    ids, _total = await search_agents(conn, model_ids=[m1])
    assert a1.id in ids
    assert a2.id not in ids


async def test_tool_ids_filter(conn, redis_client):
    t1 = await conn.fetchval(
        "INSERT INTO tools_resource (name) VALUES ($1) RETURNING id", f"t-{_u()}"
    )
    t2 = await conn.fetchval(
        "INSERT INTO tools_resource (name) VALUES ($1) RETURNING id", f"t-{_u()}"
    )
    a1 = await create_agent(conn, tool_ids=[t1])
    a2 = await create_agent(conn, tool_ids=[t2])
    ids, _total = await search_agents(conn, tool_ids=[t1])
    assert a1.id in ids
    assert a2.id not in ids


async def test_exclude_ids(conn, redis_client):
    name = await create_name(conn, f"excl-{_u()}", redis_client)
    a1 = await create_agent(conn, name_id=name.id)
    a2 = await create_agent(conn, name_id=name.id)
    ids, _total = await search_agents(conn, exclude_ids=[a1.id])
    assert a1.id not in ids
    assert a2.id in ids


async def test_pagination(conn, redis_client):
    tag = _u()
    created = []
    for i in range(5):
        name = await create_name(conn, f"page-{tag}-{i:02d}", redis_client)
        a = await create_agent(conn, name_id=name.id)
        created.append(a.id)
    page1, _total = await search_agents(
        conn, search=f"page-{tag}", limit_count=2, offset_count=0
    )
    page2, _total = await search_agents(
        conn, search=f"page-{tag}", limit_count=2, offset_count=2
    )
    page3, _total = await search_agents(
        conn, search=f"page-{tag}", limit_count=2, offset_count=4
    )
    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    all_ids = page1 + page2 + page3
    assert len(set(all_ids)) == 5


async def test_active_only_default(conn, redis_client):
    a = await create_agent(conn, active=False)
    ids, _total = await search_agents(conn)
    assert a.id not in ids


async def test_active_only_false_includes_inactive(conn, redis_client):
    name = await create_name(conn, f"inactive-{_u()}", redis_client)
    a = await create_agent(conn, active=False, name_id=name.id)
    ids, _total = await search_agents(conn, search=name.name, active_only=False)
    assert a.id in ids
