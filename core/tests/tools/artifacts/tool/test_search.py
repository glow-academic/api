"""Tests for search_tools — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.tool.create import create_tool
from app.tools.artifacts.tool.search import search_tools
from app.tools.resources.departments.create import create_department
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


async def test_bare_search_returns_results(conn, redis_client):
    name = await create_name(conn, f"bare-{_u()}", redis_client)
    t = await create_tool(conn, name_id=name.id)
    ids, _total = await search_tools(conn)
    assert t.id in ids


async def test_text_search_filters_by_name(conn, redis_client):
    tag = _u()
    name_match = await create_name(conn, f"match-{tag}", redis_client)
    name_other = await create_name(conn, f"other-{_u()}", redis_client)
    t1 = await create_tool(conn, name_id=name_match.id)
    t2 = await create_tool(conn, name_id=name_other.id)
    ids, _total = await search_tools(conn, search=f"match-{tag}")
    assert t1.id in ids
    assert t2.id not in ids


async def test_text_search_filters_by_description(conn, redis_client):
    tag = _u()
    desc = await create_description(conn, f"desc-{tag}", redis_client)
    t1 = await create_tool(conn, description_id=desc.id)
    t2 = await create_tool(conn)
    ids, _total = await search_tools(conn, search=f"desc-{tag}")
    assert t1.id in ids
    assert t2.id not in ids


async def test_department_filter(conn, redis_client):
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)
    t1 = await create_tool(conn, department_ids=[d1.id])
    t2 = await create_tool(conn, department_ids=[d2.id])
    ids, _total = await search_tools(conn, department_ids=[d1.id])
    assert t1.id in ids
    assert t2.id not in ids


async def test_exclude_ids(conn, redis_client):
    tag = _u()
    n1 = await create_name(conn, f"excl-{tag}-a", redis_client)
    n2 = await create_name(conn, f"excl-{tag}-b", redis_client)
    t1 = await create_tool(conn, name_id=n1.id)
    t2 = await create_tool(conn, name_id=n2.id)
    ids, _total = await search_tools(conn, search=f"excl-{tag}", exclude_ids=[t1.id])
    assert t1.id not in ids
    assert t2.id in ids


async def test_pagination(conn, redis_client):
    tag = _u()
    created = []
    for i in range(5):
        name = await create_name(conn, f"page-{tag}-{i:02d}", redis_client)
        t = await create_tool(conn, name_id=name.id)
        created.append(t.id)
    page1, _total = await search_tools(
        conn, search=f"page-{tag}", limit_count=2, offset_count=0
    )
    page2, _total = await search_tools(
        conn, search=f"page-{tag}", limit_count=2, offset_count=2
    )
    page3, _total = await search_tools(
        conn, search=f"page-{tag}", limit_count=2, offset_count=4
    )
    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    all_ids = page1 + page2 + page3
    assert len(set(all_ids)) == 5


async def test_active_only_default(conn, redis_client):
    t = await create_tool(conn, active=False)
    ids, _total = await search_tools(conn)
    assert t.id not in ids


async def test_active_only_false_includes_inactive(conn, redis_client):
    name = await create_name(conn, f"inactive-{_u()}", redis_client)
    t = await create_tool(conn, active=False, name_id=name.id)
    ids, _total = await search_tools(conn, search=name.name, active_only=False)
    assert t.id in ids
