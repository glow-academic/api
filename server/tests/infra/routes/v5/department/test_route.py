"""End-to-end tests for the canonical department HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import create_admin_route_actor


@dataclass(frozen=True)
class DepartmentRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str
    setting_id: UUID


async def _create_department_route_resources(
    pool, redis_client
) -> DepartmentRouteResources:
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.names.create import create_name
    from app.tools.resources.settings.create import create_setting

    tag = unique_tag()
    name = f"Route Department {tag}"
    description = f"Route department description {tag}"

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)
        setting_res = await create_setting(conn, redis=redis_client)

    return DepartmentRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
        setting_id=setting_res.id,
    )


@pytest_asyncio.fixture
async def department_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["department", "setting", "persona"],
        group_name="department-route",
        role_name_prefix="Department Route Admin",
        role="superadmin",
    )


@pytest.mark.asyncio
class TestDepartmentRoute:
    async def test_create_department_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        v5_department_route_client,
        department_route_actor,
    ):
        resources = await _create_department_route_resources(pool, redis_client)
        v5_department_route_client.authenticate(
            profile_id=department_route_actor.profile_id,
            session_id=department_route_actor.session_id,
        )

        response = await v5_department_route_client.client.post(
            "/v5/departments/create",
            json={
                "departments": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "settings_ids": [str(resources.setting_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "departments"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["department_id"] is not None

    async def test_get_department_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        v5_department_route_client,
        department_route_actor,
    ):
        created = await self._create_department_via_route(
            pool,
            redis_client,
            v5_department_route_client,
            department_route_actor,
        )

        response = await v5_department_route_client.client.post(
            "/v5/departments/get",
            json={"department_id": created["department_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "departments"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["actor_name"] == department_route_actor.name
        assert payload["department_exists"] is True
        assert payload["group_id"] is not None
        assert payload["names"]["resource"]["name"] == created["name"]
        assert (
            payload["descriptions"]["resource"]["description"] == created["description"]
        )

    async def test_search_department_route_returns_created_department(
        self,
        pool,
        redis_client,
        v5_department_route_client,
        department_route_actor,
    ):
        created = await self._create_department_via_route(
            pool,
            redis_client,
            v5_department_route_client,
            department_route_actor,
        )

        response = await v5_department_route_client.client.post(
            "/v5/departments/search",
            json={
                "search": created["name"],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "departments"
        payload = response.json()
        assert payload["actor_name"] == department_route_actor.name
        assert payload["total_count"] >= 1
        assert any(
            department["department_id"] == created["department_id"]
            for department in payload["departments"]
        )

    async def test_update_department_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        v5_department_route_client,
        department_route_actor,
    ):
        created = await self._create_department_via_route(
            pool,
            redis_client,
            v5_department_route_client,
            department_route_actor,
        )
        updated = await _create_department_route_resources(pool, redis_client)

        response = await v5_department_route_client.client.post(
            "/v5/departments/update",
            json={
                "departments": [
                    {
                        "department_id": created["department_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "settings_ids": [str(updated.setting_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "departments"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["department_id"] == created["department_id"]

    async def test_delete_department_route_soft_deletes_department(
        self,
        pool,
        redis_client,
        v5_department_route_client,
        department_route_actor,
    ):
        created = await self._create_department_via_route(
            pool,
            redis_client,
            v5_department_route_client,
            department_route_actor,
        )

        response = await v5_department_route_client.client.post(
            "/v5/departments/delete",
            json={"department_ids": [created["department_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "departments"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["department_id"] == created["department_id"]

    async def test_duplicate_department_route_creates_new_department(
        self,
        pool,
        redis_client,
        v5_department_route_client,
        department_route_actor,
    ):
        created = await self._create_department_via_route(
            pool,
            redis_client,
            v5_department_route_client,
            department_route_actor,
        )

        response = await v5_department_route_client.client.post(
            "/v5/departments/duplicate",
            json={"department_id": created["department_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "departments"
        payload = response.json()
        assert payload["success"] is True
        assert payload["department_id"] != created["department_id"]

    async def test_department_draft_route_creates_server_authoritative_draft(
        self,
        pool,
        redis_client,
        v5_department_route_client,
        department_route_actor,
    ):
        resources = await _create_department_route_resources(pool, redis_client)
        v5_department_route_client.authenticate(
            profile_id=department_route_actor.profile_id,
            session_id=department_route_actor.session_id,
        )

        response = await v5_department_route_client.client.patch(
            "/v5/departments/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "setting_ids": [str(resources.setting_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "departments,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["draft_id"] is not None
        assert payload["new_version"] == 1
        assert payload["form_state"]["name_id"] == str(resources.name_id)

    async def test_department_drafts_route_lists_owned_drafts(
        self,
        pool,
        redis_client,
        v5_department_route_client,
        department_route_actor,
    ):
        resources = await _create_department_route_resources(pool, redis_client)
        v5_department_route_client.authenticate(
            profile_id=department_route_actor.profile_id,
            session_id=department_route_actor.session_id,
        )
        draft_response = await v5_department_route_client.client.patch(
            "/v5/departments/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
            },
        )
        assert draft_response.status_code == 200, draft_response.text

        response = await v5_department_route_client.client.post(
            "/v5/departments/drafts",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "departments,drafts"
        payload = response.json()
        assert payload["entries"]
        assert any(
            entry["id"] == draft_response.json()["draft_id"]
            for entry in payload["entries"]
        )

    async def test_department_docs_route_returns_composed_docs(
        self,
        v5_department_route_client,
        department_route_actor,
    ):
        v5_department_route_client.authenticate(
            profile_id=department_route_actor.profile_id,
            session_id=department_route_actor.session_id,
        )

        response = await v5_department_route_client.client.post(
            "/v5/departments/docs",
            json={"entity_id": None},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "department"
        assert payload["type"] == "artifact"
        assert payload["page_metadata"]["list"]["title"] == "Departments"

    async def test_department_export_route_returns_csv_upload(
        self,
        pool,
        redis_client,
        v5_department_route_client,
        department_route_actor,
    ):
        created = await self._create_department_via_route(
            pool,
            redis_client,
            v5_department_route_client,
            department_route_actor,
        )

        response = await v5_department_route_client.client.post(
            "/v5/departments/export",
            json={"department_id": created["department_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] >= 1

    async def test_department_refresh_route_returns_invalidated_tags(
        self,
        v5_department_route_client,
        department_route_actor,
    ):
        v5_department_route_client.authenticate(
            profile_id=department_route_actor.profile_id,
            session_id=department_route_actor.session_id,
        )

        response = await v5_department_route_client.client.post(
            "/v5/departments/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "departments,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["invalidated_tags"] == ["departments", "artifacts"]

    async def _create_department_via_route(
        self,
        pool,
        redis_client,
        v5_department_route_client,
        department_route_actor,
    ) -> dict[str, str]:
        resources = await _create_department_route_resources(pool, redis_client)
        v5_department_route_client.authenticate(
            profile_id=department_route_actor.profile_id,
            session_id=department_route_actor.session_id,
        )

        response = await v5_department_route_client.client.post(
            "/v5/departments/create",
            json={
                "departments": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "settings_ids": [str(resources.setting_id)],
                    }
                ]
            },
        )
        assert response.status_code == 200, response.text
        department_id = response.json()["results"][0]["department_id"]

        return {
            "department_id": department_id,
            "name": resources.name,
            "description": resources.description,
        }
