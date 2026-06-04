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
        dashboard_route_client,
        dashboard_route_actor,
    ):
        dashboard_route_client.authenticate(
            profile_id=dashboard_route_actor.profile_id,
            session_id=dashboard_route_actor.session_id,
        )

        response = await dashboard_route_client.client.post(
            "/dashboard",
            json={"role_ids": [str(dashboard_route_actor.role_id)]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "artifacts,dashboard,views,analytics"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["header_metrics"]
        assert payload["primary_metrics"]
        assert payload["secondary_metrics"]
        # Attempt history is no longer inline on the dashboard GET bundle
        # (DashboardBundleResponse.history is always null — fetch via
        # /attempt/dashboard/search).
        assert payload["history"] is None
        assert payload["analytics"] is not None
        role_options = payload["analytics"]["role_options"]
        assert any(
            option["id"] == str(dashboard_route_actor.role_id)
            and option["value"] == str(dashboard_route_actor.role_id)
            for option in role_options
        )

    # NOTE: removed test_search_dashboard_route_returns_history,
    # test_dashboard_docs_route_returns_composed_docs,
    # test_dashboard_export_route_returns_current_contract, and
    # test_dashboard_refresh_route_returns_invalidated_tags — the dashboard
    # search/docs/export/refresh operations were consolidated into the
    # attempt/system parents (`/system/sessions`-style lists, `/system/context`,
    # view-aware `/system/export`, `/system/refresh`). The dashboard artifact
    # exposes only the root `POST /dashboard` bundle; there are no
    # `/dashboard/{search,docs,export,refresh}` routes and the dashboard route
    # client mounts only the root dashboard module.
