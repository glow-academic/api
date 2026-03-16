"""Tests for search_models — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.model.create import create_model
from app.tools.artifacts.model.search import search_models
from app.tools.resources.departments.create import create_department
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


async def test_bare_search_returns_results(conn, redis_client):
    name = await create_name(conn, f"bare-{_u()}", redis_client)
    m = await create_model(conn, name_id=name.id)
    ids, _total = await search_models(conn)
    assert m.id in ids


async def test_text_search_filters_by_name(conn, redis_client):
    tag = _u()
    name_match = await create_name(conn, f"match-{tag}", redis_client)
    name_other = await create_name(conn, f"other-{_u()}", redis_client)
    m1 = await create_model(conn, name_id=name_match.id)
    m2 = await create_model(conn, name_id=name_other.id)
    ids, _total = await search_models(conn, search=f"match-{tag}")
    assert m1.id in ids
    assert m2.id not in ids


async def test_text_search_filters_by_description(conn, redis_client):
    tag = _u()
    desc = await create_description(conn, f"desc-{tag}", redis_client)
    m1 = await create_model(conn, description_id=desc.id)
    m2 = await create_model(conn)
    ids, _total = await search_models(conn, search=f"desc-{tag}")
    assert m1.id in ids
    assert m2.id not in ids


async def test_department_filter(conn, redis_client):
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)
    m1 = await create_model(conn, department_ids=[d1.id])
    m2 = await create_model(conn, department_ids=[d2.id])
    ids, _total = await search_models(conn, department_ids=[d1.id])
    assert m1.id in ids
    assert m2.id not in ids


async def test_provider_ids_filter(conn, redis_client):
    p1 = await conn.fetchval(
        "INSERT INTO providers_resource DEFAULT VALUES RETURNING id"
    )
    p2 = await conn.fetchval(
        "INSERT INTO providers_resource DEFAULT VALUES RETURNING id"
    )
    m1 = await create_model(conn, provider_ids=[p1])
    m2 = await create_model(conn, provider_ids=[p2])
    ids, _total = await search_models(conn, provider_ids=[p1])
    assert m1.id in ids
    assert m2.id not in ids


async def test_exclude_ids(conn, redis_client):
    name = await create_name(conn, f"excl-{_u()}", redis_client)
    m1 = await create_model(conn, name_id=name.id)
    m2 = await create_model(conn, name_id=name.id)
    ids, _total = await search_models(conn, exclude_ids=[m1.id])
    assert m1.id not in ids
    assert m2.id in ids


async def test_pagination(conn, redis_client):
    tag = _u()
    created = []
    for i in range(5):
        name = await create_name(conn, f"page-{tag}-{i:02d}", redis_client)
        m = await create_model(conn, name_id=name.id)
        created.append(m.id)
    page1, _total = await search_models(
        conn, search=f"page-{tag}", limit_count=2, offset_count=0
    )
    page2, _total = await search_models(
        conn, search=f"page-{tag}", limit_count=2, offset_count=2
    )
    page3, _total = await search_models(
        conn, search=f"page-{tag}", limit_count=2, offset_count=4
    )
    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    all_ids = page1 + page2 + page3
    assert len(set(all_ids)) == 5


async def test_active_only_default(conn, redis_client):
    m = await create_model(conn, active=False)
    ids, _total = await search_models(conn)
    assert m.id not in ids


async def test_active_only_false_includes_inactive(conn, redis_client):
    name = await create_name(conn, f"inactive-{_u()}", redis_client)
    m = await create_model(conn, active=False, name_id=name.id)
    ids, _total = await search_models(conn, search=name.name, active_only=False)
    assert m.id in ids
