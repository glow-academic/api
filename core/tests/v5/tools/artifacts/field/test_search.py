"""Tests for search_fields — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.field.create import create_field
from app.tools.artifacts.field.search import search_fields
from app.tools.resources.departments.create import create_department
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_bare_search_returns_results(conn, redis_client):
    """A field with a name should appear in an unfiltered search."""
    name = await create_name(conn, f"bare-{_u()}", redis_client)
    f = await create_field(conn, name_id=name.id)

    ids, _total = await search_fields(conn)
    assert f.id in ids


async def test_text_search_filters_by_name(conn, redis_client):
    """Text search matches name substring."""
    tag = _u()
    name_match = await create_name(conn, f"match-{tag}", redis_client)
    name_other = await create_name(conn, f"other-{_u()}", redis_client)

    f1 = await create_field(conn, name_id=name_match.id)
    f2 = await create_field(conn, name_id=name_other.id)

    ids, _total = await search_fields(conn, search=f"match-{tag}")
    assert f1.id in ids
    assert f2.id not in ids


async def test_text_search_filters_by_description(conn, redis_client):
    """Text search also matches description text."""
    tag = _u()
    desc = await create_description(conn, f"desc-{tag}", redis_client)

    f1 = await create_field(conn, description_id=desc.id)
    f2 = await create_field(conn)

    ids, _total = await search_fields(conn, search=f"desc-{tag}")
    assert f1.id in ids
    assert f2.id not in ids


async def test_department_filter(conn, redis_client):
    """Filter by department_ids returns only matching fields."""
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)

    f1 = await create_field(conn, department_ids=[d1.id])
    f2 = await create_field(conn, department_ids=[d2.id])

    ids, _total = await search_fields(conn, department_ids=[d1.id])
    assert f1.id in ids
    assert f2.id not in ids


async def test_exclude_ids(conn, redis_client):
    """Excluded fields should not appear in results."""
    tag = _u()
    n1 = await create_name(conn, f"excl-{tag}-a", redis_client)
    n2 = await create_name(conn, f"excl-{tag}-b", redis_client)
    f1 = await create_field(conn, name_id=n1.id)
    f2 = await create_field(conn, name_id=n2.id)

    ids, _total = await search_fields(conn, search=f"excl-{tag}", exclude_ids=[f1.id])
    assert f1.id not in ids
    assert f2.id in ids


async def test_pagination(conn, redis_client):
    """Pagination with limit and offset works."""
    tag = _u()
    created = []
    for i in range(5):
        name = await create_name(conn, f"page-{tag}-{i:02d}", redis_client)
        f = await create_field(conn, name_id=name.id)
        created.append(f.id)

    page1, _total = await search_fields(
        conn, search=f"page-{tag}", limit_count=2, offset_count=0
    )
    page2, _total = await search_fields(
        conn, search=f"page-{tag}", limit_count=2, offset_count=2
    )
    page3, _total = await search_fields(
        conn, search=f"page-{tag}", limit_count=2, offset_count=4
    )

    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    # No overlap
    all_ids = page1 + page2 + page3
    assert len(set(all_ids)) == 5


async def test_active_only_default(conn, redis_client):
    """Inactive fields excluded by default."""
    f = await create_field(conn, active=False)

    ids, _total = await search_fields(conn)
    assert f.id not in ids


async def test_active_only_false_includes_inactive(conn, redis_client):
    """active_only=False includes inactive fields."""
    name = await create_name(conn, f"inactive-{_u()}", redis_client)
    f = await create_field(conn, active=False, name_id=name.id)

    ids, _total = await search_fields(conn, search=name.name, active_only=False)
    assert f.id in ids
