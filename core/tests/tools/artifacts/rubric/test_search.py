"""Tests for search_rubrics — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.rubric.create import create_rubric
from app.tools.artifacts.rubric.search import search_rubrics
from app.tools.artifacts.simulation.create import create_simulation
from app.tools.artifacts.simulation.update import update_simulation
from app.tools.resources.departments.create import create_department
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.names.create import create_name
from app.tools.resources.rubrics.create import create_rubric as create_rubric_resource
from app.tools.resources.scenario_rubrics.create import create_scenario_rubric
from app.tools.resources.scenarios.create import create_scenario as create_scenario_resource

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_bare_search_returns_results(conn, redis_client):
    """A rubric with a name should appear in an unfiltered search."""
    name = await create_name(conn, f"bare-{_u()}", redis_client)
    r = await create_rubric(conn, name_id=name.id)

    ids, _total = await search_rubrics(conn)
    assert r.id in ids


async def test_text_search_filters_by_name(conn, redis_client):
    """Text search matches name substring."""
    tag = _u()
    name_match = await create_name(conn, f"match-{tag}", redis_client)
    name_other = await create_name(conn, f"other-{_u()}", redis_client)

    r1 = await create_rubric(conn, name_id=name_match.id)
    r2 = await create_rubric(conn, name_id=name_other.id)

    ids, _total = await search_rubrics(conn, search=f"match-{tag}")
    assert r1.id in ids
    assert r2.id not in ids


async def test_text_search_filters_by_description(conn, redis_client):
    """Text search also matches description text."""
    tag = _u()
    desc = await create_description(conn, f"desc-{tag}", redis_client)

    r1 = await create_rubric(conn, description_id=desc.id)
    r2 = await create_rubric(conn)

    ids, _total = await search_rubrics(conn, search=f"desc-{tag}")
    assert r1.id in ids
    assert r2.id not in ids


async def test_department_filter(conn, redis_client):
    """Filter by department_ids returns only matching rubrics."""
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)

    r1 = await create_rubric(conn, department_ids=[d1.id])
    r2 = await create_rubric(conn, department_ids=[d2.id])

    ids, _total = await search_rubrics(conn, department_ids=[d1.id])
    assert r1.id in ids
    assert r2.id not in ids


async def test_exclude_ids(conn, redis_client):
    """Excluded rubrics should not appear in results."""
    name = await create_name(conn, f"excl-{_u()}", redis_client)
    r1 = await create_rubric(conn, name_id=name.id)
    r2 = await create_rubric(conn, name_id=name.id)

    ids, _total = await search_rubrics(conn, exclude_ids=[r1.id])
    assert r1.id not in ids
    assert r2.id in ids


async def test_pagination(conn, redis_client):
    """Pagination with limit and offset works."""
    tag = _u()
    created = []
    for i in range(5):
        name = await create_name(conn, f"page-{tag}-{i:02d}", redis_client)
        r = await create_rubric(conn, name_id=name.id)
        created.append(r.id)

    page1, _total = await search_rubrics(
        conn, search=f"page-{tag}", limit_count=2, offset_count=0
    )
    page2, _total = await search_rubrics(
        conn, search=f"page-{tag}", limit_count=2, offset_count=2
    )
    page3, _total = await search_rubrics(
        conn, search=f"page-{tag}", limit_count=2, offset_count=4
    )

    assert len(page1) == 2
    assert len(page2) == 2
    assert len(page3) == 1
    # No overlap
    all_ids = page1 + page2 + page3
    assert len(set(all_ids)) == 5


async def test_active_only_default(conn, redis_client):
    """Inactive rubrics excluded by default."""
    r = await create_rubric(conn, active=False)

    ids, _total = await search_rubrics(conn)
    assert r.id not in ids


async def test_active_only_false_includes_inactive(conn, redis_client):
    """active_only=False includes inactive rubrics."""
    name = await create_name(conn, f"inactive-{_u()}", redis_client)
    r = await create_rubric(conn, active=False, name_id=name.id)

    ids, _total = await search_rubrics(conn, search=name.name, active_only=False)
    assert r.id in ids


async def test_simulation_filter_excludes_soft_removed_link(conn, redis_client):
    """L1: a soft-removed scenario↔rubric link must not leak into the
    simulation-filtered rubric search.

    Chain: rubric ← scenario_rubrics_resource (srr) → scenario, and a simulation
    linking that scenario + that srr (via simulation_scenario_rubrics_junction).
    While the junction is active the rubric matches simulation_ids=[sim]. After
    the rubric link is removed (update_simulation deactivates the junction) the
    rubric must no longer match — search must agree with the simulation detail
    view, which filters active junctions.
    """
    # scenario_rubrics_resource.rubric_id FKs rubrics_resource, and the
    # simulation-filter join matches rubric_artifact.id; build both the resource
    # row and the artifact row under the same id so the rubric is searchable.
    rubric_res = await create_rubric_resource(
        conn, redis_client, name=f"sim-rubric-{_u()}"
    )
    await create_rubric(conn, id=rubric_res.id)
    scenario_res = await create_scenario_resource(
        conn, redis_client, name=f"sim-scenario-{_u()}"
    )
    srr = await create_scenario_rubric(
        conn, scenario_id=scenario_res.id, rubric_id=rubric_res.id, redis=redis_client
    )
    sim = await create_simulation(
        conn,
        scenario_ids=[scenario_res.id],
        scenario_rubric_ids=[srr.id],
    )

    # Active link: rubric is reachable via the simulation filter.
    ids, _total = await search_rubrics(conn, simulation_ids=[sim.id])
    assert rubric_res.id in ids

    # Soft-remove the rubric link (deactivates simulation_scenario_rubrics_junction).
    await update_simulation(conn, sim.id, scenario_rubric_ids=[])

    ids_after, _total_after = await search_rubrics(conn, simulation_ids=[sim.id])
    assert rubric_res.id not in ids_after  # soft-removed link no longer leaks
