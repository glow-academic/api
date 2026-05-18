"""Tests for search_providers — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.provider.create import create_provider
from app.tools.artifacts.provider.search import search_providers
from app.tools.resources.departments.create import create_department
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


async def test_bare_search_returns_results(conn, redis_client):
    name = await create_name(conn, f"bare-{_u()}", redis_client)
    p = await create_provider(conn, name_id=name.id)
    ids, _total = await search_providers(conn)
    assert p.id in ids


async def test_text_search_filters_by_name(conn, redis_client):
    tag = _u()
    name_match = await create_name(conn, f"match-{tag}", redis_client)
    name_other = await create_name(conn, f"other-{_u()}", redis_client)
    p1 = await create_provider(conn, name_id=name_match.id)
    p2 = await create_provider(conn, name_id=name_other.id)
    ids, _total = await search_providers(conn, search=f"match-{tag}")
    assert p1.id in ids
    assert p2.id not in ids


async def test_text_search_filters_by_description(conn, redis_client):
    tag = _u()
    desc = await create_description(conn, f"desc-{tag}", redis_client)
    p1 = await create_provider(conn, description_id=desc.id)
    p2 = await create_provider(conn)
    ids, _total = await search_providers(conn, search=f"desc-{tag}")
    assert p1.id in ids
    assert p2.id not in ids


async def test_department_filter(conn, redis_client):
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)
    p1 = await create_provider(conn, department_ids=[d1.id])
    p2 = await create_provider(conn, department_ids=[d2.id])
    ids, _total = await search_providers(conn, department_ids=[d1.id])
    assert p1.id in ids
    assert p2.id not in ids


async def test_exclude_ids(conn, redis_client):
    name = await create_name(conn, f"excl-{_u()}", redis_client)
    p1 = await create_provider(conn, name_id=name.id)
    p2 = await create_provider(conn, name_id=name.id)
    ids, _total = await search_providers(conn, exclude_ids=[p1.id])
    assert p1.id not in ids
    assert p2.id in ids


async def test_pagination(conn, redis_client):
    tag = _u()
    created = []
    for i in range(5):
        name = await create_name(conn, f"page-{tag}-{i:02d}", redis_client)
        p = await create_provider(conn, name_id=name.id)
        created.append(p.id)
    page1, _total = await search_providers(
        conn, search=f"page-{tag}", limit_count=2, offset_count=0
    )
    page2, _total = await search_providers(
        conn, search=f"page-{tag}", limit_count=2, offset_count=2
    )
    page3, _total = await search_providers(
        conn, search=f"page-{tag}", limit_count=2, offset_count=4
    )
    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    all_ids = page1 + page2 + page3
    assert len(set(all_ids)) == 5


async def test_active_only_default(conn, redis_client):
    p = await create_provider(conn, active=False)
    ids, _total = await search_providers(conn)
    assert p.id not in ids


async def test_active_only_false_includes_inactive(conn, redis_client):
    name = await create_name(conn, f"inactive-{_u()}", redis_client)
    p = await create_provider(conn, active=False, name_id=name.id)
    ids, _total = await search_providers(conn, search=name.name, active_only=False)
    assert p.id in ids
