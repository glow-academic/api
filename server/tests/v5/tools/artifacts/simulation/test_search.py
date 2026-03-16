"""Tests for search_simulations — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.simulation.create import create_simulation
from app.tools.artifacts.simulation.search import search_simulations
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
    """A simulation with a name should appear in an unfiltered search."""
    name = await create_name(conn, f"bare-{_u()}", redis_client)
    s = await create_simulation(conn, name_id=name.id)

    ids, _total = await search_simulations(conn)
    assert s.id in ids


async def test_text_search_filters_by_name(conn, redis_client):
    """Text search matches name substring."""
    tag = _u()
    name_match = await create_name(conn, f"match-{tag}", redis_client)
    name_other = await create_name(conn, f"other-{_u()}", redis_client)

    s1 = await create_simulation(conn, name_id=name_match.id)
    s2 = await create_simulation(conn, name_id=name_other.id)

    ids, _total = await search_simulations(conn, search=f"match-{tag}")
    assert s1.id in ids
    assert s2.id not in ids


async def test_text_search_filters_by_description(conn, redis_client):
    """Text search also matches description text."""
    tag = _u()
    desc = await create_description(conn, f"desc-{tag}", redis_client)

    s1 = await create_simulation(conn, description_id=desc.id)
    s2 = await create_simulation(conn)

    ids, _total = await search_simulations(conn, search=f"desc-{tag}")
    assert s1.id in ids
    assert s2.id not in ids


async def test_department_filter(conn, redis_client):
    """Filter by department_ids returns only matching simulations."""
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)

    s1 = await create_simulation(conn, department_ids=[d1.id])
    s2 = await create_simulation(conn, department_ids=[d2.id])

    ids, _total = await search_simulations(conn, department_ids=[d1.id])
    assert s1.id in ids
    assert s2.id not in ids


async def test_scenario_filter(conn, redis_client):
    """Filter by scenario_ids returns only simulations with that scenario."""
    sc_id = await conn.fetchval(
        "INSERT INTO scenarios_resource DEFAULT VALUES RETURNING id"
    )

    s1 = await create_simulation(conn, scenario_ids=[sc_id])
    s2 = await create_simulation(conn)

    ids, _total = await search_simulations(conn, scenario_ids=[sc_id])
    assert s1.id in ids
    assert s2.id not in ids


async def test_exclude_ids(conn, redis_client):
    """Excluded simulations should not appear in results."""
    name = await create_name(conn, f"excl-{_u()}", redis_client)
    s1 = await create_simulation(conn, name_id=name.id)
    s2 = await create_simulation(conn, name_id=name.id)

    ids, _total = await search_simulations(conn, exclude_ids=[s1.id])
    assert s1.id not in ids
    assert s2.id in ids


async def test_pagination(conn, redis_client):
    """Pagination with limit and offset works."""
    tag = _u()
    created = []
    for i in range(5):
        name = await create_name(conn, f"page-{tag}-{i:02d}", redis_client)
        s = await create_simulation(conn, name_id=name.id)
        created.append(s.id)

    page1, _total = await search_simulations(
        conn, search=f"page-{tag}", limit_count=2, offset_count=0
    )
    page2, _total = await search_simulations(
        conn, search=f"page-{tag}", limit_count=2, offset_count=2
    )
    page3, _total = await search_simulations(
        conn, search=f"page-{tag}", limit_count=2, offset_count=4
    )

    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    # No overlap
    all_ids = page1 + page2 + page3
    assert len(set(all_ids)) == 5


async def test_active_only_default(conn, redis_client):
    """Inactive simulations excluded by default."""
    s = await create_simulation(conn, active=False)

    ids, _total = await search_simulations(conn)
    assert s.id not in ids


async def test_active_only_false_includes_inactive(conn, redis_client):
    """active_only=False includes inactive simulations."""
    name = await create_name(conn, f"inactive-{_u()}", redis_client)
    s = await create_simulation(conn, active=False, name_id=name.id)

    ids, _total = await search_simulations(conn, search=name.name, active_only=False)
    assert s.id in ids
