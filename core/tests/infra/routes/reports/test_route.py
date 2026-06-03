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
        reports_route_client,
        reports_route_actor,
    ):
        reports_route_client.authenticate(
            profile_id=reports_route_actor.profile_id,
            session_id=reports_route_actor.session_id,
        )

        response = await reports_route_client.client.post(
            "/report",
            json={
                "target_profile_id": str(reports_route_actor.profiles_id),
                "actor_profile_id": str(reports_route_actor.profile_id),
                "role_ids": [str(reports_route_actor.role_id)],
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
        role_options = payload["analytics"]["role_options"]
        assert any(
            option["id"] == str(reports_route_actor.role_id)
            and option["value"] == str(reports_route_actor.role_id)
            for option in role_options
        )
        assert payload["total_count"] >= 0

    # NOTE: removed test_reports_docs_route_returns_composed_docs,
    # test_reports_export_route_returns_current_contract, and
    # test_reports_refresh_route_returns_invalidated_tags — the reports
    # docs/export/refresh operations were consolidated into the attempt/system
    # parents (`/system/context`, view-aware `/system/export`, `/system/refresh`).
    # The reports artifact exposes only the root `POST /report` analytics bundle;
    # there are no `/report/{docs,export,refresh}` routes and the reports route
    # client mounts only the root report module.
