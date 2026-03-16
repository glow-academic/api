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
        v5_leaderboard_route_client,
        leaderboard_route_actor,
    ):
        v5_leaderboard_route_client.authenticate(
            profile_id=leaderboard_route_actor.profile_id,
            session_id=leaderboard_route_actor.session_id,
        )

        response = await v5_leaderboard_route_client.client.post(
            "/v5/leaderboard/get",
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

    async def test_search_leaderboard_route_returns_rows(
        self,
        v5_leaderboard_route_client,
        leaderboard_route_actor,
    ):
        v5_leaderboard_route_client.authenticate(
            profile_id=leaderboard_route_actor.profile_id,
            session_id=leaderboard_route_actor.session_id,
        )

        response = await v5_leaderboard_route_client.client.post(
            "/v5/leaderboard/search",
            json={
                "page_limit": 50,
                "page_offset": 0,
            },
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "artifacts,leaderboard,list"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert isinstance(payload["data"], list)
        assert payload["total_count"] >= 0
        assert "profiles" in payload["resources"]
        assert "simulations" in payload["resources"]
        assert "scenarios" in payload["resources"]

    async def test_leaderboard_docs_route_returns_composed_docs(
        self,
        v5_leaderboard_route_client,
        leaderboard_route_actor,
    ):
        v5_leaderboard_route_client.authenticate(
            profile_id=leaderboard_route_actor.profile_id,
            session_id=leaderboard_route_actor.session_id,
        )

        response = await v5_leaderboard_route_client.client.post(
            "/v5/leaderboard/docs",
            json={"entity_id": None},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "leaderboard"
        assert payload["type"] == "analytics"
        assert payload["page_metadata"]["list"]["title"] == "Leaderboard"
        op_names = {operation["name"] for operation in payload["api_operations"]}
        assert {
            "get_leaderboard",
            "search_leaderboard",
            "leaderboard_refresh",
            "export_leaderboard",
        } <= op_names

    async def test_leaderboard_export_route_returns_current_contract(
        self,
        v5_leaderboard_route_client,
        leaderboard_route_actor,
    ):
        v5_leaderboard_route_client.authenticate(
            profile_id=leaderboard_route_actor.profile_id,
            session_id=leaderboard_route_actor.session_id,
        )

        response = await v5_leaderboard_route_client.client.post(
            "/v5/leaderboard/export",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()

        if payload["row_count"] == 0:
            assert payload["content"] == ""
            assert payload["file_name"] == ""
            return

        assert payload["file_name"].endswith(".zip")
        assert payload["content"] != ""
        assert payload["row_count"] > 0

    async def test_leaderboard_refresh_route_returns_invalidated_tags(
        self,
        v5_leaderboard_route_client,
        leaderboard_route_actor,
    ):
        v5_leaderboard_route_client.authenticate(
            profile_id=leaderboard_route_actor.profile_id,
            session_id=leaderboard_route_actor.session_id,
        )

        response = await v5_leaderboard_route_client.client.post(
            "/v5/leaderboard/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "leaderboard,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["refreshed_views"] == []
        assert payload["invalidated_tags"] == ["leaderboard", "artifacts"]
