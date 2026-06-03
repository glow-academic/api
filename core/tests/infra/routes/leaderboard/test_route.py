"""End-to-end tests for the canonical leaderboard HTTP routes."""

from __future__ import annotations

import pytest
import pytest_asyncio
from tests.infra.route_helpers import create_admin_route_actor


@pytest_asyncio.fixture
async def leaderboard_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="leaderboard-route",
        role_name_prefix="Leaderboard Route Admin",
    )


@pytest.mark.asyncio
class TestLeaderboardRoute:
    async def test_get_leaderboard_route_returns_sections(
        self,
        leaderboard_route_client,
        leaderboard_route_actor,
    ):
        leaderboard_route_client.authenticate(
            profile_id=leaderboard_route_actor.profile_id,
            session_id=leaderboard_route_actor.session_id,
        )

        response = await leaderboard_route_client.client.post(
            "/leaderboard",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "artifacts,leaderboard"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["sections"]["header_metrics"]
        assert payload["sections"]["rankings"]
        assert payload["sections"]["accolades"]
        assert payload["sections"]["trends"]
        assert payload["sections"]["filters"]
        assert payload["sections"]["accolade_winners"]
        assert payload["analytics"] is not None

    # NOTE: removed test_search_leaderboard_route_returns_rows,
    # test_leaderboard_docs_route_returns_composed_docs,
    # test_leaderboard_export_route_returns_current_contract, and
    # test_leaderboard_refresh_route_returns_invalidated_tags — the leaderboard
    # search/docs/export/refresh operations were consolidated into the
    # attempt/system parents (`/system/sessions`-style lists, `/system/context`,
    # view-aware `/system/export`, `/system/refresh`). The leaderboard artifact
    # exposes only the root `POST /leaderboard` bundle; there are no
    # `/leaderboard/{search,docs,export,refresh}` routes and the leaderboard
    # route client mounts only the root leaderboard module.
