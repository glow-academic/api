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
        # /problem (system-scope) gates on the ("system", "problem") permission,
        # which is not in the default CRUD set granted by the helper.
        extra_permissions=[("system", "problem")],
        group_name="activity-route",
        role_name_prefix="Activity Route Admin",
    )


@pytest.mark.asyncio
class TestActivityRoute:
    async def test_get_activity_route_returns_summary(
        self,
        activity_route_client,
        activity_route_actor,
    ):
        activity_route_client.authenticate(
            profile_id=activity_route_actor.profile_id,
            session_id=activity_route_actor.session_id,
        )

        response = await activity_route_client.client.post(
            "/activity",
            json={
                "role_ids": [str(activity_route_actor.role_id)],
                "history_page": 0,
                "history_page_size": 10,
            },
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
        # Paginated history is no longer inline on the activity GET bundle
        # (ActivityResponse.history is always null — fetch via /system/sessions).
        assert payload["history"] is None

    # NOTE: removed test_search_activity_route_returns_sessions — the activity
    # session list was consolidated into the system parent (`/system/sessions`).
    # Activity itself now exposes only the root `POST /activity` summary; there
    # is no `/activity/search` route, and the activity route client does not
    # mount the system list module.

    async def test_activity_problem_route_creates_problem(
        self,
        activity_route_client,
        activity_route_actor,
    ):
        activity_route_client.authenticate(
            profile_id=activity_route_actor.profile_id,
            session_id=activity_route_actor.session_id,
        )

        response = await activity_route_client.client.post(
            "/problem",
            json={"type": "bug", "message": "Route-level problem report"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "system,problems"
        payload = response.json()
        assert payload["success"] is True
        UUID(payload["problem_id"])

    async def test_activity_resolve_route_updates_problem_state(
        self,
        activity_route_client,
        activity_route_actor,
    ):
        activity_route_client.authenticate(
            profile_id=activity_route_actor.profile_id,
            session_id=activity_route_actor.session_id,
        )

        create_response = await activity_route_client.client.post(
            "/problem",
            json={"type": "feature", "message": "Resolve me"},
        )
        assert create_response.status_code == 200, create_response.text
        problem_id = create_response.json()["problem_id"]

        resolve_response = await activity_route_client.client.post(
            "/resolve",
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

    # NOTE: removed test_activity_docs_route_returns_composed_docs,
    # test_activity_export_route_returns_current_contract, and
    # test_activity_refresh_route_returns_invalidated_tags — the activity
    # docs/export/refresh operations were consolidated into the system parent
    # (`/system/context`, view-aware `/system/export`, `/system/refresh`).
    # Activity exposes only the root `POST /activity` summary plus `/problem`
    # and `/resolve`; there are no `/activity/{docs,export,refresh}` routes and
    # the activity route client does not mount the consolidated system modules.
