"""End-to-end tests for the home and practice HTTP routes.

The 19->3 route consolidation (commit 0ffaa32903) collapsed the former
multi-endpoint home/practice stacks (`/get`, `/search`, `/export`, ...) into a
single get-bundle endpoint each, nested under the attempt router:

  - `POST /home`      (app/routes/attempt/home.py:    @router.post(""))
  - `POST /practice`  (app/routes/attempt/practice.py: @router.post(""))

The `/home/search` `/home/export` `/practice/search` `/practice/export` route
endpoints, and the `record` view-artifact in its entirety, were removed by that
consolidation (see the `record_route_client` removal note historically in
conftest.py). The stale tests for those removed endpoints have been deleted —
the attempt artifact's own `/attempt/search` and `/attempt/export` are a
separate artifact covered by `attempt_route_client`, not a home/practice
replacement.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from tests.infra.route_helpers import create_admin_route_actor


@pytest_asyncio.fixture
async def learning_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["home", "practice", "dashboard"],
        group_name="learning-route",
        role_name_prefix="Learning Route Admin",
    )


@pytest_asyncio.fixture
async def second_learning_route_actor(pool, redis_client, setting_graph_factory):
    """A distinct actor used to prove cross-profile cache isolation."""
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["home", "practice", "dashboard"],
        group_name="learning-route-2",
        role_name_prefix="Learning Route Admin Two",
    )


@pytest.mark.asyncio
class TestHomePracticeRoutes:
    @staticmethod
    def _assert_tagged_for_artifact(response, artifact: str) -> None:
        tags = response.headers["X-Cache-Tags"].split(",")
        assert artifact in tags

    async def test_get_home_route_returns_bundle(
        self,
        home_route_client,
        learning_route_actor,
    ):
        home_route_client.authenticate(
            profile_id=learning_route_actor.profile_id,
            session_id=learning_route_actor.session_id,
        )

        response = await home_route_client.client.post(
            "/home",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        self._assert_tagged_for_artifact(response, "home")
        payload = response.json()
        assert payload["actor_name"] == learning_route_actor.name
        assert isinstance(payload["items"], list)
        assert payload["analytics"] is not None

    async def test_get_practice_route_returns_bundle(
        self,
        practice_route_client,
        learning_route_actor,
    ):
        practice_route_client.authenticate(
            profile_id=learning_route_actor.profile_id,
            session_id=learning_route_actor.session_id,
        )

        response = await practice_route_client.client.post(
            "/practice",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        self._assert_tagged_for_artifact(response, "practice")
        payload = response.json()
        assert payload["actor_name"] == learning_route_actor.name
        assert isinstance(payload["items"], list)
        assert payload["analytics"] is not None

    async def test_home_cache_does_not_leak_across_profiles(
        self,
        home_route_client,
        learning_route_actor,
        second_learning_route_actor,
    ):
        """A cached /home response for one profile must not be served to
        another. The request body (GetHomeRequest) carries no profile
        identity, so a cache key built from the body alone collides across
        all profiles and leaks profile A's home (actor_name, sims, stats)
        to profile B. The cache key must be scoped to the actor's profile_id.
        """
        # Profile A: warm the cache (NO bypass header → response is cached).
        home_route_client.authenticate(
            profile_id=learning_route_actor.profile_id,
            session_id=learning_route_actor.session_id,
        )
        resp_a = await home_route_client.client.post("/home", json={})
        assert resp_a.status_code == 200, resp_a.text
        assert resp_a.json()["actor_name"] == learning_route_actor.name

        # Profile B: identical request body, same un-bypassed cache path.
        home_route_client.authenticate(
            profile_id=second_learning_route_actor.profile_id,
            session_id=second_learning_route_actor.session_id,
        )
        resp_b = await home_route_client.client.post("/home", json={})
        assert resp_b.status_code == 200, resp_b.text

        # B must get its OWN home, never A's cached response.
        assert resp_b.json()["actor_name"] == second_learning_route_actor.name

    async def test_practice_cache_does_not_leak_across_profiles(
        self,
        practice_route_client,
        learning_route_actor,
        second_learning_route_actor,
    ):
        """Same cross-profile isolation guarantee for the /practice route."""
        practice_route_client.authenticate(
            profile_id=learning_route_actor.profile_id,
            session_id=learning_route_actor.session_id,
        )
        resp_a = await practice_route_client.client.post("/practice", json={})
        assert resp_a.status_code == 200, resp_a.text
        assert resp_a.json()["actor_name"] == learning_route_actor.name

        practice_route_client.authenticate(
            profile_id=second_learning_route_actor.profile_id,
            session_id=second_learning_route_actor.session_id,
        )
        resp_b = await practice_route_client.client.post("/practice", json={})
        assert resp_b.status_code == 200, resp_b.text

        assert resp_b.json()["actor_name"] == second_learning_route_actor.name
