"""Tests for search_profiles — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.profile.create import create_profile
from app.tools.artifacts.profile.search import search_profiles
from app.tools.resources.departments.create import create_department
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_bare_search_returns_results(conn, redis_client):
    """A profile with a name should appear in an unfiltered search."""
    name = await create_name(conn, f"bare-{_u()}", redis_client)
    p = await create_profile(conn, name_id=name.id)

    ids, _total = await search_profiles(conn)
    assert p.id in ids


async def test_text_search_filters_by_name(conn, redis_client):
    """Text search matches name substring."""
    tag = _u()
    name_match = await create_name(conn, f"match-{tag}", redis_client)
    name_other = await create_name(conn, f"other-{_u()}", redis_client)

    p1 = await create_profile(conn, name_id=name_match.id)
    p2 = await create_profile(conn, name_id=name_other.id)

    ids, _total = await search_profiles(conn, search=f"match-{tag}")
    assert p1.id in ids
    assert p2.id not in ids


async def test_department_filter(conn, redis_client):
    """Filter by department_ids returns only matching profiles."""
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)

    p1 = await create_profile(conn, department_ids=[d1.id])
    p2 = await create_profile(conn, department_ids=[d2.id])

    ids, _total = await search_profiles(conn, department_ids=[d1.id])
    assert p1.id in ids
    assert p2.id not in ids


async def test_exclude_ids(conn, redis_client):
    """Excluded profiles should not appear in results."""
    name = await create_name(conn, f"excl-{_u()}", redis_client)
    p1 = await create_profile(conn, name_id=name.id)
    p2 = await create_profile(conn, name_id=name.id)

    ids, _total = await search_profiles(conn, exclude_ids=[p1.id])
    assert p1.id not in ids
    assert p2.id in ids


async def test_pagination(conn, redis_client):
    """Pagination with limit and offset works."""
    tag = _u()
    created = []
    for i in range(5):
        name = await create_name(conn, f"page-{tag}-{i:02d}", redis_client)
        p = await create_profile(conn, name_id=name.id)
        created.append(p.id)

    page1, _total = await search_profiles(
        conn, search=f"page-{tag}", limit_count=2, offset_count=0
    )
    page2, _total = await search_profiles(
        conn, search=f"page-{tag}", limit_count=2, offset_count=2
    )
    page3, _total = await search_profiles(
        conn, search=f"page-{tag}", limit_count=2, offset_count=4
    )

    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    # No overlap
    all_ids = page1 + page2 + page3
    assert len(set(all_ids)) == 5


async def test_active_only_default(conn, redis_client):
    """Inactive profiles excluded by default."""
    p = await create_profile(conn, active=False)

    ids, _total = await search_profiles(conn)
    assert p.id not in ids


async def test_active_only_false_includes_inactive(conn, redis_client):
    """active_only=False includes inactive profiles."""
    name = await create_name(conn, f"inactive-{_u()}", redis_client)
    p = await create_profile(conn, active=False, name_id=name.id)

    ids, _total = await search_profiles(conn, search=name.name, active_only=False)
    assert p.id in ids
