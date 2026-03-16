"""End-to-end tests for the canonical activity HTTP routes."""

from __future__ import annotations

from uuid import UUID

import pytest
import pytest_asyncio
from tests.infra.route_helpers import create_admin_route_actor


@pytest_asyncio.fixture
async def activity_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="activity-route",
        role_name_prefix="Activity Route Admin",
    )


@pytest.mark.asyncio
class TestActivityRoute:
    async def test_get_activity_route_returns_summary(
        self,
        v5_activity_route_client,
        activity_route_actor,
    ):
        v5_activity_route_client.authenticate(
            profile_id=activity_route_actor.profile_id,
            session_id=activity_route_actor.session_id,
        )

        response = await v5_activity_route_client.client.post(
            "/v5/activity/get",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "artifacts,activity"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["sessions_count"] >= 0
        assert payload["active_profiles_count"] >= 0
        assert payload["profile_summary"] is not None
        assert payload["resources"]["profiles"] is not None
        assert payload["analytics"] is not None

    async def test_search_activity_route_returns_sessions(
        self,
        v5_activity_route_client,
        activity_route_actor,
    ):
        v5_activity_route_client.authenticate(
            profile_id=activity_route_actor.profile_id,
            session_id=activity_route_actor.session_id,
        )

        response = await v5_activity_route_client.client.post(
            "/v5/activity/search",
            json={"page": 0, "page_size": 50},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "artifacts,activity,list"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert isinstance(payload["data"], list)
        assert payload["total_count"] >= 0
        assert payload["page"] == 0
        assert payload["page_size"] == 50

    async def test_activity_problem_route_creates_problem(
        self,
        v5_activity_route_client,
        activity_route_actor,
    ):
        v5_activity_route_client.authenticate(
            profile_id=activity_route_actor.profile_id,
            session_id=activity_route_actor.session_id,
        )

        response = await v5_activity_route_client.client.post(
            "/v5/activity/problem",
            json={"type": "bug", "message": "Route-level problem report"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "problems,views,activity"
        payload = response.json()
        assert payload["success"] is True
        UUID(payload["problem_id"])

    async def test_activity_resolve_route_updates_problem_state(
        self,
        v5_activity_route_client,
        activity_route_actor,
    ):
        v5_activity_route_client.authenticate(
            profile_id=activity_route_actor.profile_id,
            session_id=activity_route_actor.session_id,
        )

        create_response = await v5_activity_route_client.client.post(
            "/v5/activity/problem",
            json={"type": "feature", "message": "Resolve me"},
        )
        assert create_response.status_code == 200, create_response.text
        problem_id = create_response.json()["problem_id"]

        resolve_response = await v5_activity_route_client.client.post(
            "/v5/activity/resolve",
            json={"problem_id": problem_id, "resolved": True},
        )

        assert resolve_response.status_code == 200, resolve_response.text
        assert (
            resolve_response.headers["X-Invalidate-Tags"]
            == "problems,views,activity,summary"
        )
        payload = resolve_response.json()
        assert payload["problem_id"] == problem_id
        assert payload["resolved"] is True
        assert payload["updated_at"] is not None

    async def test_activity_docs_route_returns_composed_docs(
        self,
        v5_activity_route_client,
        activity_route_actor,
    ):
        v5_activity_route_client.authenticate(
            profile_id=activity_route_actor.profile_id,
            session_id=activity_route_actor.session_id,
        )

        response = await v5_activity_route_client.client.post(
            "/v5/activity/docs",
            json={"entity_id": None},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "activity"
        assert payload["type"] == "analytics"
        assert payload["page_metadata"]["list"]["title"] == "Activity"
        op_names = {operation["name"] for operation in payload["api_operations"]}
        assert {
            "get_activity",
            "search_activity",
            "create_problem",
            "resolve_problem",
            "activity_refresh",
            "export_activity",
        } <= op_names

    async def test_activity_export_route_returns_current_contract(
        self,
        v5_activity_route_client,
        activity_route_actor,
    ):
        v5_activity_route_client.authenticate(
            profile_id=activity_route_actor.profile_id,
            session_id=activity_route_actor.session_id,
        )

        response = await v5_activity_route_client.client.post(
            "/v5/activity/export",
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

    async def test_activity_refresh_route_returns_invalidated_tags(
        self,
        v5_activity_route_client,
        activity_route_actor,
    ):
        v5_activity_route_client.authenticate(
            profile_id=activity_route_actor.profile_id,
            session_id=activity_route_actor.session_id,
        )

        response = await v5_activity_route_client.client.post(
            "/v5/activity/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "activity,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["refreshed_views"] == ["activity_mv"]
        assert payload["invalidated_tags"] == ["activity", "artifacts"]
