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
