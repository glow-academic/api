"""Tests for search_cohorts — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.cohort.create import create_cohort
from app.tools.artifacts.cohort.search import search_cohorts
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
    """A cohort with a name should appear in an unfiltered search."""
    name = await create_name(conn, f"bare-{_u()}", redis_client)
    c = await create_cohort(conn, name_id=name.id)

    ids, _total = await search_cohorts(conn)
    assert c.id in ids


async def test_text_search_filters_by_name(conn, redis_client):
    """Text search matches name substring."""
    tag = _u()
    name_match = await create_name(conn, f"match-{tag}", redis_client)
    name_other = await create_name(conn, f"other-{_u()}", redis_client)

    c1 = await create_cohort(conn, name_id=name_match.id)
    c2 = await create_cohort(conn, name_id=name_other.id)

    ids, _total = await search_cohorts(conn, search=f"match-{tag}")
    assert c1.id in ids
    assert c2.id not in ids


async def test_text_search_filters_by_description(conn, redis_client):
    """Text search also matches description text."""
    tag = _u()
    desc = await create_description(conn, f"desc-{tag}", redis_client)

    c1 = await create_cohort(conn, description_id=desc.id)
    c2 = await create_cohort(conn)

    ids, _total = await search_cohorts(conn, search=f"desc-{tag}")
    assert c1.id in ids
    assert c2.id not in ids


async def test_department_filter(conn, redis_client):
    """Filter by department_ids returns only matching cohorts."""
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)

    c1 = await create_cohort(conn, department_ids=[d1.id])
    c2 = await create_cohort(conn, department_ids=[d2.id])

    ids, _total = await search_cohorts(conn, department_ids=[d1.id])
    assert c1.id in ids
    assert c2.id not in ids


async def test_simulation_filter(conn, redis_client):
    """Filter by simulation_ids returns only matching cohorts."""
    s1 = await conn.fetchval(
        "INSERT INTO simulations_resource DEFAULT VALUES RETURNING id"
    )
    s2 = await conn.fetchval(
        "INSERT INTO simulations_resource DEFAULT VALUES RETURNING id"
    )

    c1 = await create_cohort(conn, simulation_ids=[s1])
    c2 = await create_cohort(conn, simulation_ids=[s2])

    ids, _total = await search_cohorts(conn, simulation_ids=[s1])
    assert c1.id in ids
    assert c2.id not in ids


async def test_profile_filter(conn, redis_client):
    """Filter by profile_ids returns only matching cohorts."""
    pr1 = await conn.fetchval(
        "INSERT INTO profiles_resource DEFAULT VALUES RETURNING id"
    )
    pr2 = await conn.fetchval(
        "INSERT INTO profiles_resource DEFAULT VALUES RETURNING id"
    )

    c1 = await create_cohort(conn, profile_ids=[pr1])
    c2 = await create_cohort(conn, profile_ids=[pr2])

    ids, _total = await search_cohorts(conn, profile_ids=[pr1])
    assert c1.id in ids
    assert c2.id not in ids


async def test_exclude_ids(conn, redis_client):
    """Excluded cohorts should not appear in results."""
    name = await create_name(conn, f"excl-{_u()}", redis_client)
    c1 = await create_cohort(conn, name_id=name.id)
    c2 = await create_cohort(conn, name_id=name.id)

    ids, _total = await search_cohorts(conn, exclude_ids=[c1.id])
    assert c1.id not in ids
    assert c2.id in ids


async def test_pagination(conn, redis_client):
    """Pagination with limit and offset works."""
    tag = _u()
    created = []
    for i in range(5):
        name = await create_name(conn, f"page-{tag}-{i:02d}", redis_client)
        c = await create_cohort(conn, name_id=name.id)
        created.append(c.id)

    page1, _total = await search_cohorts(
        conn, search=f"page-{tag}", limit_count=2, offset_count=0
    )
    page2, _total = await search_cohorts(
        conn, search=f"page-{tag}", limit_count=2, offset_count=2
    )
    page3, _total = await search_cohorts(
        conn, search=f"page-{tag}", limit_count=2, offset_count=4
    )

    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    # No overlap
    all_ids = page1 + page2 + page3
    assert len(set(all_ids)) == 5


async def test_active_only_default(conn, redis_client):
    """Inactive cohorts excluded by default."""
    c = await create_cohort(conn, active=False)

    ids, _total = await search_cohorts(conn)
    assert c.id not in ids


async def test_active_only_false_includes_inactive(conn, redis_client):
    """active_only=False includes inactive cohorts."""
    name = await create_name(conn, f"inactive-{_u()}", redis_client)
    c = await create_cohort(conn, active=False, name_id=name.id)

    ids, _total = await search_cohorts(conn, search=name.name, active_only=False)
    assert c.id in ids
