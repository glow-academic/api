"""Cross-profile cache-isolation test for ``POST /pricing``.

Same class as the #191 (/attempt/home) and #193/#194 (/attempt/get) cache
leaks. ``get_pricing`` caches the pricing bundle, but the bundle embeds
per-actor ``analytics`` facets — ``get_pricing_impl`` builds
``resolve_analytics_facets`` scoped to the caller's ``profile`` (its
``department_ids`` drive ``department_options``). The ``PricingRequest`` body
carries no actor identity, so a key built from the body alone collides across
all callers: profile A warms the cache, then profile B (in a different
department) is served A's cached bundle on a hit — B sees A's department in
its analytics facets (cross-profile leak).

Fails pre-fix (B receives A's department_options) and passes once the cache
key includes ``user_ctx=str(profile_id)``.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from tests.infra.route_helpers import create_admin_route_actor


@pytest_asyncio.fixture
async def pricing_actor_a(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="pricing-cache-a",
        role_name_prefix="Pricing Cache A",
    )


@pytest_asyncio.fixture
async def pricing_actor_b(pool, redis_client, setting_graph_factory):
    """A DISTINCT actor in its own department (own setting graph)."""
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="pricing-cache-b",
        role_name_prefix="Pricing Cache B",
    )


def _dept_values(payload: dict) -> set[str]:
    analytics = payload.get("analytics") or {}
    return {o["value"] for o in (analytics.get("department_options") or [])}


@pytest.mark.asyncio
async def test_pricing_cache_does_not_leak_across_profiles(
    pricing_route_client,
    pricing_actor_a,
    pricing_actor_b,
):
    assert pricing_actor_a.department_id != pricing_actor_b.department_id

    # Actor A: warm the cache (NO bypass header → bundle is cached).
    pricing_route_client.authenticate(
        profile_id=pricing_actor_a.profile_id,
        session_id=pricing_actor_a.session_id,
    )
    resp_a = await pricing_route_client.client.post("/pricing", json={})
    assert resp_a.status_code == 200, resp_a.text
    payload_a = resp_a.json()
    assert resp_a.headers["X-Cache-Hit"] == "0"
    a_depts = _dept_values(payload_a)
    assert str(pricing_actor_a.department_id) in a_depts

    # Actor B: identical request body, same un-bypassed cache path. B is in a
    # different department, so its analytics facets must list ITS department —
    # never A's cached, A-scoped facets.
    pricing_route_client.authenticate(
        profile_id=pricing_actor_b.profile_id,
        session_id=pricing_actor_b.session_id,
    )
    resp_b = await pricing_route_client.client.post("/pricing", json={})
    assert resp_b.status_code == 200, resp_b.text
    payload_b = resp_b.json()
    b_depts = _dept_values(payload_b)

    # The leak: pre-fix, B is served A's cached bundle (B sees A's department,
    # not its own). Post-fix, B gets its own scoped facets.
    assert str(pricing_actor_b.department_id) in b_depts, (
        "cross-profile leak: profile B was served profile A's cached pricing "
        "bundle (B's own department missing from its facets)"
    )
    assert str(pricing_actor_a.department_id) not in b_depts, (
        "cross-profile leak: profile B's analytics facets contain profile A's "
        "department — A's cached, A-scoped bundle was served to B"
    )
