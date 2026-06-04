"""Cross-profile cache-isolation test for ``get_leaderboard_impl_cached``.

Same class as the #191 (/attempt/home) and #193/#194 (/attempt/get) cache
leaks. ``get_leaderboard_impl_cached`` caches the leaderboard bundle, but the
bundle embeds per-actor ``analytics`` facets — ``resolve_analytics_facets``
scopes ``department_options`` to the caller's ``profile.department_ids``. The
``LeaderboardRequest`` body carries no actor identity, so a key built from the
body alone collides across all callers: profile A warms the cache, then
profile B (in a different department) is served A's cached bundle on a hit —
B sees A's department in its analytics facets (cross-profile leak).

The impl is the shared cache layer behind BOTH the ``POST /leaderboard`` HTTP
route and the leaderboard WS handler (``app.ws.attempt.leaderboard.get``), so a
warm written by one actor on either transport is read by the next actor with
the same body. Testing at the impl is the faithful repro: the HTTP route wraps
each read in ``run_artifact_operation_with_audit``, whose audit write
invalidates the shared HTTP cache tag on every call and masks the leak in a
two-request sequence — but the underlying ``get_leaderboard_impl_cached`` key
collision (exploited by the WS path and by concurrent reads inside the TTL)
remains.

Fails pre-fix (B's bundle carries A's department) and passes once the cache
key includes ``user_ctx=str(profile_id)``.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from tests.infra.route_helpers import create_admin_route_actor

from app.infra.leaderboard.get import get_leaderboard_impl_cached
from app.infra.leaderboard.types import LeaderboardRequest


@pytest_asyncio.fixture
async def leaderboard_actor_a(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="leaderboard-cache-a",
        role_name_prefix="Leaderboard Cache A",
    )


@pytest_asyncio.fixture
async def leaderboard_actor_b(pool, redis_client, setting_graph_factory):
    """A DISTINCT actor in its own department (own setting graph)."""
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="leaderboard-cache-b",
        role_name_prefix="Leaderboard Cache B",
    )


def _dept_values(response) -> set[str]:
    if not response.analytics:
        return set()
    return {o.value for o in response.analytics.department_options}


@pytest.mark.asyncio
async def test_leaderboard_cache_does_not_leak_across_profiles(
    pool,
    redis_client,
    leaderboard_actor_a,
    leaderboard_actor_b,
):
    assert leaderboard_actor_a.department_id != leaderboard_actor_b.department_id

    # Actor A: warm the shared impl cache (NO bypass → bundle is cached).
    resp_a, hit_a = await get_leaderboard_impl_cached(
        pool,
        LeaderboardRequest(),
        profile_id=leaderboard_actor_a.profile_id,
        cache_key_path="/leaderboard",
    )
    assert hit_a is False
    a_depts = _dept_values(resp_a)
    assert str(leaderboard_actor_a.department_id) in a_depts

    # Actor B: identical request body, same un-bypassed cache path. B is in a
    # different department, so its analytics facets must list ITS department —
    # never A's cached, A-scoped facets.
    resp_b, _hit_b = await get_leaderboard_impl_cached(
        pool,
        LeaderboardRequest(),
        profile_id=leaderboard_actor_b.profile_id,
        cache_key_path="/leaderboard",
    )
    b_depts = _dept_values(resp_b)

    # The leak: pre-fix, B is served A's cached bundle (B sees A's department,
    # not its own). Post-fix, B gets its own scoped facets.
    assert str(leaderboard_actor_b.department_id) in b_depts, (
        "cross-profile leak: profile B was served profile A's cached "
        "leaderboard bundle (B's own department missing from its facets)"
    )
    assert str(leaderboard_actor_a.department_id) not in b_depts, (
        "cross-profile leak: profile B's analytics facets contain profile A's "
        "department — A's cached, A-scoped bundle was served to B"
    )
