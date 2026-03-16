"""End-to-end tests for the canonical parameter HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import create_admin_route_actor


@dataclass(frozen=True)
class ParameterRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str
    department_id: UUID
    field_id: UUID


async def _create_parameter_route_resources(
    pool, redis_client
) -> ParameterRouteResources:
    from app.tools.resources.departments.create import create_department
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.fields.create import create_field
    from app.tools.resources.names.create import create_name

    tag = unique_tag()
    name = f"Route Parameter {tag}"
    description = f"Route parameter description {tag}"

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)
        department_res = await create_department(conn, redis=redis_client)
        field_res = await create_field(
            conn,
            f"Route Param Field {tag}",
            redis=redis_client,
        )

    return ParameterRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
        department_id=department_res.id,
        field_id=field_res.id,
    )


@pytest_asyncio.fixture
async def parameter_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["parameter", "agent", "persona"],
        group_name="parameter-route",
        role_name_prefix="Parameter Route Admin",
    )


@pytest.mark.asyncio
class TestParameterRoute:
    async def test_create_parameter_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        v5_parameter_route_client,
        parameter_route_actor,
    ):
        resources = await _create_parameter_route_resources(pool, redis_client)
        v5_parameter_route_client.authenticate(
            profile_id=parameter_route_actor.profile_id,
            session_id=parameter_route_actor.session_id,
        )

        response = await v5_parameter_route_client.client.post(
            "/v5/parameters/create",
            json={
                "parameters": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(parameter_route_actor.department_id)],
                        "field_ids": [str(resources.field_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "parameters"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["parameter_id"] is not None

    async def test_get_parameter_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        v5_parameter_route_client,
        parameter_route_actor,
    ):
        created = await self._create_parameter_via_route(
            pool,
            redis_client,
            v5_parameter_route_client,
            parameter_route_actor,
        )

        response = await v5_parameter_route_client.client.post(
            "/v5/parameters/get",
            json={"parameter_id": created["parameter_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "parameters"
        payload = response.json()
        assert payload["actor_name"] == parameter_route_actor.name
        assert payload["parameter_exists"] is True
        assert payload["group_id"] is not None
        assert payload["names"]["resource"]["name"] == created["name"]
        assert (
            payload["descriptions"]["resource"]["description"] == created["description"]
        )

    async def test_search_parameter_route_returns_created_parameter(
        self,
        pool,
        redis_client,
        v5_parameter_route_client,
        parameter_route_actor,
    ):
        created = await self._create_parameter_via_route(
            pool,
            redis_client,
            v5_parameter_route_client,
            parameter_route_actor,
        )

        response = await v5_parameter_route_client.client.post(
            "/v5/parameters/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(parameter_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "parameters"
        payload = response.json()
        assert payload["actor_name"] == parameter_route_actor.name
        assert payload["total_count"] >= 1
        assert any(
            parameter["parameter_id"] == created["parameter_id"]
            for parameter in payload["parameters"]
        )

    async def test_update_parameter_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        v5_parameter_route_client,
        parameter_route_actor,
    ):
        created = await self._create_parameter_via_route(
            pool,
            redis_client,
            v5_parameter_route_client,
            parameter_route_actor,
        )
        updated = await _create_parameter_route_resources(pool, redis_client)

        response = await v5_parameter_route_client.client.post(
            "/v5/parameters/update",
            json={
                "parameters": [
                    {
                        "parameter_id": created["parameter_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "department_ids": [str(parameter_route_actor.department_id)],
                        "field_ids": [str(updated.field_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "parameters"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_delete_parameter_route_soft_deletes_parameter(
        self,
        pool,
        redis_client,
        v5_parameter_route_client,
        parameter_route_actor,
    ):
        created = await self._create_parameter_via_route(
            pool,
            redis_client,
            v5_parameter_route_client,
            parameter_route_actor,
        )

        response = await v5_parameter_route_client.client.post(
            "/v5/parameters/delete",
            json={"parameter_ids": [created["parameter_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "parameters"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_duplicate_parameter_route_creates_new_parameter(
        self,
        pool,
        redis_client,
        v5_parameter_route_client,
        parameter_route_actor,
    ):
        created = await self._create_parameter_via_route(
            pool,
            redis_client,
            v5_parameter_route_client,
            parameter_route_actor,
        )

        response = await v5_parameter_route_client.client.post(
            "/v5/parameters/duplicate",
            json={"parameter_id": created["parameter_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "parameters"
        payload = response.json()
        assert payload["success"] is True
        assert payload["parameter_id"] != created["parameter_id"]

    async def test_parameter_draft_route_creates_server_authoritative_draft(
        self,
        pool,
        redis_client,
        v5_parameter_route_client,
        parameter_route_actor,
    ):
        resources = await _create_parameter_route_resources(pool, redis_client)
        v5_parameter_route_client.authenticate(
            profile_id=parameter_route_actor.profile_id,
            session_id=parameter_route_actor.session_id,
        )

        response = await v5_parameter_route_client.client.patch(
            "/v5/parameters/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(parameter_route_actor.department_id)],
                "field_ids": [str(resources.field_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "parameters,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["draft_id"] is not None
        assert payload["new_version"] == 1
        assert payload["form_state"]["name_id"] == str(resources.name_id)

    async def test_parameter_drafts_route_lists_owned_drafts(
        self,
        pool,
        redis_client,
        v5_parameter_route_client,
        parameter_route_actor,
    ):
        resources = await _create_parameter_route_resources(pool, redis_client)
        v5_parameter_route_client.authenticate(
            profile_id=parameter_route_actor.profile_id,
            session_id=parameter_route_actor.session_id,
        )

        draft_response = await v5_parameter_route_client.client.patch(
            "/v5/parameters/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(parameter_route_actor.department_id)],
            },
        )
        assert draft_response.status_code == 200, draft_response.text
        draft_id = draft_response.json()["draft_id"]

        response = await v5_parameter_route_client.client.post(
            "/v5/parameters/drafts",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "parameters,drafts"
        payload = response.json()
        assert any(entry["id"] == draft_id for entry in (payload["entries"] or []))

    async def test_parameter_docs_route_returns_composed_docs(
        self,
        v5_parameter_route_client,
        parameter_route_actor,
    ):
        v5_parameter_route_client.authenticate(
            profile_id=parameter_route_actor.profile_id,
            session_id=parameter_route_actor.session_id,
        )

        response = await v5_parameter_route_client.client.post(
            "/v5/parameters/docs",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "parameter"
        assert payload["type"] == "artifact"
        assert payload["artifact"] is not None
        assert payload["api_operations"]

    async def test_parameter_export_route_returns_csv_upload(
        self,
        pool,
        redis_client,
        v5_parameter_route_client,
        parameter_route_actor,
    ):
        created = await self._create_parameter_via_route(
            pool,
            redis_client,
            v5_parameter_route_client,
            parameter_route_actor,
        )

        response = await v5_parameter_route_client.client.post(
            "/v5/parameters/export",
            json={"parameter_id": created["parameter_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] == 1

    async def test_parameter_refresh_route_returns_invalidated_tags(
        self,
        v5_parameter_route_client,
        parameter_route_actor,
    ):
        v5_parameter_route_client.authenticate(
            profile_id=parameter_route_actor.profile_id,
            session_id=parameter_route_actor.session_id,
        )

        response = await v5_parameter_route_client.client.post(
            "/v5/parameters/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "parameters,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["invalidated_tags"] == ["parameters", "artifacts"]

    async def _create_parameter_via_route(
        self,
        pool,
        redis_client,
        v5_parameter_route_client,
        parameter_route_actor,
    ) -> dict[str, str]:
        resources = await _create_parameter_route_resources(pool, redis_client)
        v5_parameter_route_client.authenticate(
            profile_id=parameter_route_actor.profile_id,
            session_id=parameter_route_actor.session_id,
        )

        response = await v5_parameter_route_client.client.post(
            "/v5/parameters/create",
            json={
                "parameters": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(parameter_route_actor.department_id)],
                        "field_ids": [str(resources.field_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        return {
            "parameter_id": payload["results"][0]["parameter_id"],
            "name": resources.name,
            "description": resources.description,
        }
