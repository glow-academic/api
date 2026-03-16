"""End-to-end tests for the canonical rubric HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import create_admin_route_actor


@dataclass(frozen=True)
class RubricRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str


async def _create_rubric_route_resources(pool, redis_client) -> RubricRouteResources:
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.names.create import create_name

    tag = unique_tag()
    name = f"Route Rubric {tag}"
    description = f"Route rubric description {tag}"

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)

    return RubricRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
    )


@pytest_asyncio.fixture
async def rubric_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["rubric", "agent", "persona"],
        group_name="rubric-route",
        role_name_prefix="Rubric Route Admin",
        role="superadmin",
    )


@pytest.mark.asyncio
class TestRubricRoute:
    async def test_create_rubric_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        v5_rubric_route_client,
        rubric_route_actor,
    ):
        resources = await _create_rubric_route_resources(pool, redis_client)
        v5_rubric_route_client.authenticate(
            profile_id=rubric_route_actor.profile_id,
            session_id=rubric_route_actor.session_id,
        )

        response = await v5_rubric_route_client.client.post(
            "/v5/rubrics/create",
            json={
                "rubrics": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(rubric_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "rubrics"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["rubric_id"] is not None

    async def test_get_rubric_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        v5_rubric_route_client,
        rubric_route_actor,
    ):
        created = await self._create_rubric_via_route(
            pool,
            redis_client,
            v5_rubric_route_client,
            rubric_route_actor,
        )

        response = await v5_rubric_route_client.client.post(
            "/v5/rubrics/get",
            json={"rubric_id": created["rubric_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "rubrics"
        payload = response.json()
        assert payload["actor_name"] == rubric_route_actor.name
        assert payload["rubric_exists"] is True
        assert payload["group_id"] is not None
        assert payload["names"]["resource"]["name"] == created["name"]
        assert (
            payload["descriptions"]["resource"]["description"] == created["description"]
        )

    async def test_search_rubric_route_returns_created_rubric(
        self,
        pool,
        redis_client,
        v5_rubric_route_client,
        rubric_route_actor,
    ):
        created = await self._create_rubric_via_route(
            pool,
            redis_client,
            v5_rubric_route_client,
            rubric_route_actor,
        )

        response = await v5_rubric_route_client.client.post(
            "/v5/rubrics/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(rubric_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "rubrics"
        payload = response.json()
        assert payload["actor_name"] == rubric_route_actor.name
        assert payload["total_count"] >= 1
        assert any(
            rubric["rubric_id"] == created["rubric_id"] for rubric in payload["rubrics"]
        )

    async def test_update_rubric_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        v5_rubric_route_client,
        rubric_route_actor,
    ):
        created = await self._create_rubric_via_route(
            pool,
            redis_client,
            v5_rubric_route_client,
            rubric_route_actor,
        )
        updated = await _create_rubric_route_resources(pool, redis_client)

        response = await v5_rubric_route_client.client.post(
            "/v5/rubrics/update",
            json={
                "rubrics": [
                    {
                        "rubric_id": created["rubric_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "department_ids": [str(rubric_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "rubrics"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_delete_rubric_route_soft_deletes_rubric(
        self,
        pool,
        redis_client,
        v5_rubric_route_client,
        rubric_route_actor,
    ):
        created = await self._create_rubric_via_route(
            pool,
            redis_client,
            v5_rubric_route_client,
            rubric_route_actor,
        )

        response = await v5_rubric_route_client.client.post(
            "/v5/rubrics/delete",
            json={"rubric_ids": [created["rubric_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "rubrics"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_duplicate_rubric_route_creates_new_rubric(
        self,
        pool,
        redis_client,
        v5_rubric_route_client,
        rubric_route_actor,
    ):
        created = await self._create_rubric_via_route(
            pool,
            redis_client,
            v5_rubric_route_client,
            rubric_route_actor,
        )

        response = await v5_rubric_route_client.client.post(
            "/v5/rubrics/duplicate",
            json={"rubric_id": created["rubric_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "rubrics"
        payload = response.json()
        assert payload["success"] is True
        assert payload["rubric_id"] != created["rubric_id"]

    async def test_rubric_draft_route_creates_server_authoritative_draft(
        self,
        pool,
        redis_client,
        v5_rubric_route_client,
        rubric_route_actor,
    ):
        resources = await _create_rubric_route_resources(pool, redis_client)
        v5_rubric_route_client.authenticate(
            profile_id=rubric_route_actor.profile_id,
            session_id=rubric_route_actor.session_id,
        )

        response = await v5_rubric_route_client.client.patch(
            "/v5/rubrics/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(rubric_route_actor.department_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "rubrics,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["draft_id"] is not None
        assert payload["new_version"] == 1
        assert payload["form_state"]["name_id"] == str(resources.name_id)

    async def test_rubric_drafts_route_lists_owned_drafts(
        self,
        pool,
        redis_client,
        v5_rubric_route_client,
        rubric_route_actor,
    ):
        resources = await _create_rubric_route_resources(pool, redis_client)
        v5_rubric_route_client.authenticate(
            profile_id=rubric_route_actor.profile_id,
            session_id=rubric_route_actor.session_id,
        )

        draft_response = await v5_rubric_route_client.client.patch(
            "/v5/rubrics/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(rubric_route_actor.department_id)],
            },
        )
        assert draft_response.status_code == 200, draft_response.text
        draft_id = draft_response.json()["draft_id"]

        response = await v5_rubric_route_client.client.post(
            "/v5/rubrics/drafts",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "rubrics,drafts"
        payload = response.json()
        assert any(entry["id"] == draft_id for entry in (payload["entries"] or []))

    async def test_rubric_docs_route_returns_composed_docs(
        self,
        v5_rubric_route_client,
        rubric_route_actor,
    ):
        v5_rubric_route_client.authenticate(
            profile_id=rubric_route_actor.profile_id,
            session_id=rubric_route_actor.session_id,
        )

        response = await v5_rubric_route_client.client.post(
            "/v5/rubrics/docs",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "rubric"
        assert payload["type"] == "artifact"
        assert payload["artifact"] is not None
        assert payload["api_operations"]

    async def test_rubric_export_route_returns_csv_upload(
        self,
        pool,
        redis_client,
        v5_rubric_route_client,
        rubric_route_actor,
    ):
        created = await self._create_rubric_via_route(
            pool,
            redis_client,
            v5_rubric_route_client,
            rubric_route_actor,
        )

        response = await v5_rubric_route_client.client.post(
            "/v5/rubrics/export",
            json={"rubric_id": created["rubric_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] == 1

    async def test_rubric_refresh_route_returns_invalidated_tags(
        self,
        v5_rubric_route_client,
        rubric_route_actor,
    ):
        v5_rubric_route_client.authenticate(
            profile_id=rubric_route_actor.profile_id,
            session_id=rubric_route_actor.session_id,
        )

        response = await v5_rubric_route_client.client.post(
            "/v5/rubrics/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "rubrics,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["invalidated_tags"] == ["rubrics", "artifacts"]

    async def _create_rubric_via_route(
        self,
        pool,
        redis_client,
        v5_rubric_route_client,
        rubric_route_actor,
    ) -> dict[str, str]:
        resources = await _create_rubric_route_resources(pool, redis_client)
        v5_rubric_route_client.authenticate(
            profile_id=rubric_route_actor.profile_id,
            session_id=rubric_route_actor.session_id,
        )

        response = await v5_rubric_route_client.client.post(
            "/v5/rubrics/create",
            json={
                "rubrics": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(rubric_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        return {
            "rubric_id": payload["results"][0]["rubric_id"],
            "name": resources.name,
            "description": resources.description,
        }
