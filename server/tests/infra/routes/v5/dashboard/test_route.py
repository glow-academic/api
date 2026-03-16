"""End-to-end tests for the canonical dashboard HTTP routes."""

from __future__ import annotations

import pytest
import pytest_asyncio
from tests.infra.route_helpers import create_admin_route_actor


@pytest_asyncio.fixture
async def dashboard_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="dashboard-route",
        role_name_prefix="Dashboard Route Admin",
    )


@pytest.mark.asyncio
class TestDashboardRoute:
    async def test_get_dashboard_route_returns_bundle(
        self,
        v5_dashboard_route_client,
        dashboard_route_actor,
    ):
        v5_dashboard_route_client.authenticate(
            profile_id=dashboard_route_actor.profile_id,
            session_id=dashboard_route_actor.session_id,
        )

        response = await v5_dashboard_route_client.client.post(
            "/v5/dashboard/get",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "artifacts,dashboard,views,analytics"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["header_metrics"]
        assert payload["primary_metrics"]
        assert payload["secondary_metrics"]
        assert payload["history"]
        assert payload["analytics"] is not None

    async def test_search_dashboard_route_returns_history(
        self,
        v5_dashboard_route_client,
        dashboard_route_actor,
    ):
        v5_dashboard_route_client.authenticate(
            profile_id=dashboard_route_actor.profile_id,
            session_id=dashboard_route_actor.session_id,
        )

        response = await v5_dashboard_route_client.client.post(
            "/v5/dashboard/search",
            json={
                "page": 0,
                "page_size": 20,
            },
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "artifacts,dashboard,list"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert isinstance(payload["data"], list)
        assert payload["total_count"] >= 0
        assert payload["page"] == 0
        assert payload["page_size"] == 20

    async def test_dashboard_docs_route_returns_composed_docs(
        self,
        v5_dashboard_route_client,
        dashboard_route_actor,
    ):
        v5_dashboard_route_client.authenticate(
            profile_id=dashboard_route_actor.profile_id,
            session_id=dashboard_route_actor.session_id,
        )

        response = await v5_dashboard_route_client.client.post(
            "/v5/dashboard/docs",
            json={"entity_id": None},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "dashboard"
        assert payload["type"] == "analytics"
        assert payload["page_metadata"]["list"]["title"] == "Dashboard"
        op_names = {operation["name"] for operation in payload["api_operations"]}
        assert {
            "get_dashboard",
            "search_dashboard",
            "dashboard_refresh",
            "export_dashboard",
        } <= op_names

    async def test_dashboard_export_route_returns_current_contract(
        self,
        v5_dashboard_route_client,
        dashboard_route_actor,
    ):
        v5_dashboard_route_client.authenticate(
            profile_id=dashboard_route_actor.profile_id,
            session_id=dashboard_route_actor.session_id,
        )

        response = await v5_dashboard_route_client.client.post(
            "/v5/dashboard/export",
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

    async def test_dashboard_refresh_route_returns_invalidated_tags(
        self,
        v5_dashboard_route_client,
        dashboard_route_actor,
    ):
        v5_dashboard_route_client.authenticate(
            profile_id=dashboard_route_actor.profile_id,
            session_id=dashboard_route_actor.session_id,
        )

        response = await v5_dashboard_route_client.client.post(
            "/v5/dashboard/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "dashboard,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["refreshed_views"] == []
        assert payload["invalidated_tags"] == ["dashboard", "artifacts"]
