"""Pagination total-count correctness for ``/system/groups`` under an
in-memory model/profile/agent filter.

``groups_system_impl`` applies the model/profile/agent filters in memory
(Phase 2a): it derives ``matching_group_ids`` from the resolved ``runs`` and
then filters BOTH the current page (``groups``) and the full result set
(``total_groups``) down to those ids, finally reporting
``total_count = len(total_groups)`` and a ceil-based ``total_pages``.

The bug: ``resolve_pricing_search_context`` fetched ``runs`` only for the
groups on the CURRENT page (``group_ids = [g.id for g in all_groups]``). So
every matching group that lived on a later page was absent from ``runs``,
hence absent from ``matching_group_ids``, hence dropped from ``total_groups``
— capping ``total_count`` at the page's matching count (≤ ``page_size``) and
collapsing ``total_pages`` to 1. The fix scopes ``runs`` to ``total_groups``
so the filtered count spans every page.

Concrete trace seeded here: 3 groups, each with a run linked to one shared
agent; ``page_size=2`` + ``agent_ids=[agent]`` filter. All 3 groups match.
  Pre-fix:  runs cover only page-0's 2 groups → total_count=2, total_pages=1.
  Post-fix: runs cover all 3 groups          → total_count=3, total_pages=2.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from tests.infra.route_helpers import create_admin_route_actor

from app.infra.pricing.types import ListPricingRequest
from app.infra.system.groups import groups_system_impl

pytestmark = pytest.mark.asyncio


async def _seed_group_with_agent_run(pool, redis_client, actor, *, label, agent_id):
    """Create one named group + one run linked to ``agent_id`` in the actor's
    session. Returns the group id."""
    from app.tools.entries.group_names.create import create_group_name
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.runs.create import create_run

    async with pool.acquire() as conn:
        group = await create_group(
            conn, redis_client, session_id=actor.session_id, artifact_type="system"
        )
        await create_group_name(
            conn, redis_client, group_id=group.id, name=label,
            session_id=actor.session_id,
        )
        await create_run(
            conn, redis_client, group_id=group.id,
            session_id=actor.session_id, agent_ids=[agent_id],
        )
    return group.id


@pytest_asyncio.fixture
async def groups_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="groups-filtered-total",
        role_name_prefix="Groups Filtered Total",
    )


async def test_agent_filter_total_count_spans_all_pages(
    pool, redis_client, groups_actor
):
    from app.tools.resources.agents.create import create_agent
    from app.tools.resources.models.create import create_model

    # Shared agent every group's run is linked to → the agent filter matches
    # all seeded groups, across pages.
    async with pool.acquire() as conn:
        model = await create_model(
            conn, value="gpt-filtered-total", name="Filtered Total Model",
            redis=redis_client,
        )
        agent = await create_agent(
            conn, name="Filtered Total Agent", redis=redis_client, model_id=model.id,
        )

    for i in range(3):
        await _seed_group_with_agent_run(
            pool, redis_client, groups_actor, label=f"ft-group-{i}", agent_id=agent.id,
        )

    async with pool.acquire() as conn:
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY group_names_mv")
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY groups_mv")
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")

    request = ListPricingRequest(
        agent_ids=[agent.id],
        page=0,
        page_size=2,
    )

    result = await groups_system_impl(
        pool,
        redis_client,
        profile_id=groups_actor.profile_id,
        session_id=groups_actor.session_id,
        request=request,
        bypass_cache=True,
    )

    # Page slice respects page_size.
    assert len(result.data) == 2
    # total_count must reflect ALL matching groups, not just the current page.
    # Pre-fix this was capped at 2 (the page's matching count).
    assert result.total_count == 3, (
        "filtered total_count must span every page, not just the current one"
    )
    # ceil(3 / 2) == 2 — pre-fix it collapsed to 1.
    assert result.total_pages == 2
