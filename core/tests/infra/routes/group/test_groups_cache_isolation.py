"""Cross-profile cache-isolation test for the ``POST /groups`` route.

Same class as the #191 (/attempt/home) and #193/#194 (/attempt/get) cache
leaks. The ``/groups`` route caches ``groups_system_impl``, which resolves the
groups/runs/costs list against the caller's OWN session
(``session_ids=[session_id]``) — so the cached response is per-actor. The
``ListPricingRequest`` body carries no actor identity, so a key built from the
body alone collides across all callers: a hit serves one profile's
session-scoped groups list to another (cross-profile leak).

The route wraps each read in ``run_artifact_operation_with_audit``; the audit
write invalidates the shared HTTP cache tag on the *next* audited read, so a
plain two-request A→B sequence can't observe the served-stale response
directly. This test instead asserts the cache-key *contract* the fix
establishes: after actor A warms the cache, A's session-scoped entry must be
stored ONLY under a key scoped to A's ``profile_id`` — never under the
profile-agnostic key that any other profile (B) would compute from the same
body. Pre-fix the entry sits under the unscoped key (reachable by B → leak);
post-fix it sits under A's scoped key (unreachable by B).

Fails pre-fix (unscoped key present) and passes once the cache key includes
``user_ctx=str(profile_id)``.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from tests.infra.route_helpers import create_admin_route_actor

from app.infra.pricing.types import ListPricingRequest
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached


async def _seed_session_group(pool, redis_client, actor, *, group_label: str) -> str:
    """Create a named group + costed run in ``actor``'s own session.

    ``groups_system_impl`` resolves ``/groups`` against ``actor.session_id``
    so this group is only visible to that actor — it is the per-actor payload
    that must not leak.
    """
    from app.tools.entries.group_names.create import create_group_name
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.run_pricing.create import (
        create_run_pricing_entry_internal,
    )
    from app.tools.entries.runs.create import create_run
    from app.tools.resources.agents.create import create_agent
    from app.tools.resources.models.create import create_model
    from app.tools.resources.pricing.create import create_pricing

    async with pool.acquire() as conn:
        group = await create_group(
            conn,
            redis_client,
            session_id=actor.session_id,
            artifact_type="system",
        )
        await create_group_name(
            conn,
            redis_client,
            group_id=group.id,
            name=group_label,
            session_id=actor.session_id,
        )
        model = await create_model(
            conn,
            value=f"gpt-{group_label}",
            name=f"Model {group_label}",
            description="leak test model",
            redis=redis_client,
        )
        agent = await create_agent(
            conn,
            name=f"Agent {group_label}",
            description="leak test agent",
            redis=redis_client,
            model_id=model.id,
        )
        input_pricing = await create_pricing(
            conn, "input", 0.02, "tokens", "tokens", 1000, redis_client
        )
        run = await create_run(
            conn,
            redis_client,
            group_id=group.id,
            session_id=actor.session_id,
            agent_ids=[agent.id],
        )
        await create_run_pricing_entry_internal(
            conn,
            redis_client,
            session_id=actor.session_id,
            pricing_type="input",
            run_id=run.id,
            pricing_id=input_pricing.id,
            count=1500,
        )
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY groups_mv")
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY run_pricing_mv")
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")

    return str(group.id)


@pytest_asyncio.fixture
async def groups_actor_a(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="groups-cache-a",
        role_name_prefix="Groups Cache A",
    )


@pytest_asyncio.fixture
async def groups_actor_b(pool, redis_client, setting_graph_factory):
    """A DISTINCT actor with its own session (own setting graph)."""
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="groups-cache-b",
        role_name_prefix="Groups Cache B",
    )


@pytest.mark.asyncio
async def test_groups_cache_does_not_leak_across_profiles(
    pool,
    redis_client,
    groups_route_client,
    groups_actor_a,
    groups_actor_b,
):
    assert groups_actor_a.session_id != groups_actor_b.session_id

    group_a = await _seed_session_group(
        pool, redis_client, groups_actor_a, group_label="group-A-secret"
    )

    # Actor A: warm the cache (NO bypass header → A's session-scoped list is
    # cached). Confirm A's own group is actually in A's view.
    groups_route_client.authenticate(
        profile_id=groups_actor_a.profile_id,
        session_id=groups_actor_a.session_id,
    )
    resp_a = await groups_route_client.client.post("/groups", json={})
    assert resp_a.status_code == 200, resp_a.text
    a_ids = {item["group_id"] for item in resp_a.json().get("data", [])}
    assert group_a in a_ids

    # The body any caller computes from POST /groups {} is identical, so the
    # cache key differs across profiles ONLY if it is scoped to profile_id.
    body = ListPricingRequest().model_dump(mode="json")
    unscoped_key = cache_key("/groups", body)
    key_for_a = cache_key("/groups", body, user_ctx=str(groups_actor_a.profile_id))
    key_for_b = cache_key("/groups", body, user_ctx=str(groups_actor_b.profile_id))

    # The leak: pre-fix, A's session-scoped list sits under the unscoped key,
    # which profile B computes identically — B reads A's groups on a hit.
    assert await get_cached(unscoped_key, redis=redis_client) is None, (
        "cross-profile leak: profile A's session-scoped groups list is cached "
        "under a profile-agnostic key reachable by any other profile (B)"
    )

    # Post-fix: A's entry is keyed to A's profile_id. B's key is distinct and
    # absent, so B can never be served A's cached list.
    assert await get_cached(key_for_a, redis=redis_client) is not None, (
        "expected A's groups list to be cached under A's profile-scoped key"
    )
    assert await get_cached(key_for_b, redis=redis_client) is None, (
        "profile B's distinct scoped key must not resolve to A's cached list"
    )
