"""End-to-end tests for the canonical reports HTTP routes."""

from __future__ import annotations

import pytest
import pytest_asyncio
from tests.infra.route_helpers import create_admin_route_actor


@pytest_asyncio.fixture
async def reports_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="reports-route",
        role_name_prefix="Reports Route Admin",
    )


@pytest.mark.asyncio
class TestReportsRoute:
    async def test_search_reports_route_returns_sections(
        self,
        v5_reports_route_client,
        reports_route_actor,
    ):
        v5_reports_route_client.authenticate(
            profile_id=reports_route_actor.profile_id,
            session_id=reports_route_actor.session_id,
        )

        response = await v5_reports_route_client.client.post(
            "/v5/reports/search",
            json={
                "target_profile_id": str(reports_route_actor.profiles_id),
                "actor_profile_id": str(reports_route_actor.profile_id),
                "page_limit": 50,
                "page_offset": 0,
            },
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "artifacts,reports,views,analytics"

        payload = response.json()
        assert payload["sections"]["header_metrics"]
        assert payload["sections"]["overview"]
        assert payload["sections"]["leaderboard"]
        assert payload["sections"]["trends"]
        assert payload["sections"]["history"]
        assert payload["analytics"] is not None
        assert payload["total_count"] >= 0

    async def test_reports_docs_route_returns_composed_docs(
        self,
        v5_reports_route_client,
        reports_route_actor,
    ):
        v5_reports_route_client.authenticate(
            profile_id=reports_route_actor.profile_id,
            session_id=reports_route_actor.session_id,
        )

        response = await v5_reports_route_client.client.post(
            "/v5/reports/docs",
            json={"entity_id": None},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "reports"
        assert payload["type"] == "analytics"
        assert payload["page_metadata"]["list"]["title"] == "Reports"
        op_names = {operation["name"] for operation in payload["api_operations"]}
        assert {"get_reports", "reports_refresh", "export_reports"} <= op_names

    async def test_reports_export_route_returns_current_contract(
        self,
        v5_reports_route_client,
        reports_route_actor,
    ):
        v5_reports_route_client.authenticate(
            profile_id=reports_route_actor.profile_id,
            session_id=reports_route_actor.session_id,
        )

        response = await v5_reports_route_client.client.post(
            "/v5/reports/export",
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

    async def test_reports_refresh_route_returns_invalidated_tags(
        self,
        v5_reports_route_client,
        reports_route_actor,
    ):
        v5_reports_route_client.authenticate(
            profile_id=reports_route_actor.profile_id,
            session_id=reports_route_actor.session_id,
        )

        response = await v5_reports_route_client.client.post(
            "/v5/reports/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "reports,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["refreshed_views"] == []
        assert payload["invalidated_tags"] == ["reports", "artifacts"]
