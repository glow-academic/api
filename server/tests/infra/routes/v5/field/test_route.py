"""End-to-end tests for the canonical field HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import create_admin_route_actor


@dataclass(frozen=True)
class FieldRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str
    department_id: UUID
    conditional_parameter_id: UUID


async def _create_field_route_resources(pool, redis_client) -> FieldRouteResources:
    from app.tools.resources.conditional_parameters.create import (
        create_conditional_parameter,
    )
    from app.tools.resources.departments.create import create_department
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.names.create import create_name
    from app.tools.resources.parameters.create import create_parameter

    tag = unique_tag()
    name = f"Route Field {tag}"
    description = f"Route field description {tag}"

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)
        department_res = await create_department(conn, redis=redis_client)
        parameter_res = await create_parameter(
            conn,
            redis_client,
            name=f"Route Field Param {tag}",
            description=f"Route field param description {tag}",
        )
        conditional_parameter_res = await create_conditional_parameter(
            conn,
            parameter_res.id,
            redis_client,
        )

    return FieldRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
        department_id=department_res.id,
        conditional_parameter_id=conditional_parameter_res.id,
    )


@pytest_asyncio.fixture
async def field_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["field", "agent", "persona"],
        group_name="field-route",
        role_name_prefix="Field Route Admin",
    )


@pytest.mark.asyncio
class TestFieldRoute:
    async def test_create_field_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        v5_field_route_client,
        field_route_actor,
    ):
        resources = await _create_field_route_resources(pool, redis_client)
        v5_field_route_client.authenticate(
            profile_id=field_route_actor.profile_id,
            session_id=field_route_actor.session_id,
        )

        response = await v5_field_route_client.client.post(
            "/v5/fields/create",
            json={
                "fields": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(field_route_actor.department_id)],
                        "conditional_parameter_ids": [
                            str(resources.conditional_parameter_id)
                        ],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "fields"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["field_id"] is not None

    async def test_get_field_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        v5_field_route_client,
        field_route_actor,
    ):
        created = await self._create_field_via_route(
            pool,
            redis_client,
            v5_field_route_client,
            field_route_actor,
        )

        response = await v5_field_route_client.client.post(
            "/v5/fields/get",
            json={"field_id": created["field_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "fields"
        payload = response.json()
        assert payload["actor_name"] == field_route_actor.name
        assert payload["field_exists"] is True
        assert payload["group_id"] is not None
        assert payload["names"]["resource"]["name"] == created["name"]
        assert (
            payload["descriptions"]["resource"]["description"] == created["description"]
        )

    async def test_search_field_route_returns_created_field(
        self,
        pool,
        redis_client,
        v5_field_route_client,
        field_route_actor,
    ):
        created = await self._create_field_via_route(
            pool,
            redis_client,
            v5_field_route_client,
            field_route_actor,
        )

        response = await v5_field_route_client.client.post(
            "/v5/fields/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(field_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "fields"
        payload = response.json()
        assert payload["actor_name"] == field_route_actor.name
        assert payload["total_count"] >= 1
        assert any(
            field["field_id"] == created["field_id"] for field in payload["fields"]
        )

    async def test_update_field_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        v5_field_route_client,
        field_route_actor,
    ):
        created = await self._create_field_via_route(
            pool,
            redis_client,
            v5_field_route_client,
            field_route_actor,
        )
        updated = await _create_field_route_resources(pool, redis_client)

        response = await v5_field_route_client.client.post(
            "/v5/fields/update",
            json={
                "fields": [
                    {
                        "field_id": created["field_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "department_ids": [str(field_route_actor.department_id)],
                        "conditional_parameter_ids": [
                            str(updated.conditional_parameter_id)
                        ],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "fields"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_delete_field_route_soft_deletes_field(
        self,
        pool,
        redis_client,
        v5_field_route_client,
        field_route_actor,
    ):
        created = await self._create_field_via_route(
            pool,
            redis_client,
            v5_field_route_client,
            field_route_actor,
        )

        response = await v5_field_route_client.client.post(
            "/v5/fields/delete",
            json={"field_ids": [created["field_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "fields"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_duplicate_field_route_creates_new_field(
        self,
        pool,
        redis_client,
        v5_field_route_client,
        field_route_actor,
    ):
        created = await self._create_field_via_route(
            pool,
            redis_client,
            v5_field_route_client,
            field_route_actor,
        )

        response = await v5_field_route_client.client.post(
            "/v5/fields/duplicate",
            json={"field_id": created["field_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "fields"
        payload = response.json()
        assert payload["success"] is True
        assert payload["field_id"] != created["field_id"]

    async def test_field_draft_route_creates_server_authoritative_draft(
        self,
        pool,
        redis_client,
        v5_field_route_client,
        field_route_actor,
    ):
        resources = await _create_field_route_resources(pool, redis_client)
        v5_field_route_client.authenticate(
            profile_id=field_route_actor.profile_id,
            session_id=field_route_actor.session_id,
        )

        response = await v5_field_route_client.client.patch(
            "/v5/fields/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(field_route_actor.department_id)],
                "conditional_parameter_ids": [str(resources.conditional_parameter_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "fields,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["draft_id"] is not None
        assert payload["new_version"] == 1
        assert payload["form_state"]["name_id"] == str(resources.name_id)

    async def test_field_drafts_route_lists_owned_drafts(
        self,
        pool,
        redis_client,
        v5_field_route_client,
        field_route_actor,
    ):
        resources = await _create_field_route_resources(pool, redis_client)
        v5_field_route_client.authenticate(
            profile_id=field_route_actor.profile_id,
            session_id=field_route_actor.session_id,
        )

        draft_response = await v5_field_route_client.client.patch(
            "/v5/fields/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(field_route_actor.department_id)],
            },
        )
        assert draft_response.status_code == 200, draft_response.text
        draft_id = draft_response.json()["draft_id"]

        response = await v5_field_route_client.client.post(
            "/v5/fields/drafts",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "fields,drafts"
        payload = response.json()
        assert any(entry["id"] == draft_id for entry in (payload["entries"] or []))

    async def test_field_docs_route_returns_composed_docs(
        self,
        v5_field_route_client,
        field_route_actor,
    ):
        v5_field_route_client.authenticate(
            profile_id=field_route_actor.profile_id,
            session_id=field_route_actor.session_id,
        )

        response = await v5_field_route_client.client.post(
            "/v5/fields/docs",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "field"
        assert payload["type"] == "artifact"
        assert payload["artifact"] is not None
        assert payload["api_operations"]

    async def test_field_export_route_returns_csv_upload(
        self,
        pool,
        redis_client,
        v5_field_route_client,
        field_route_actor,
    ):
        created = await self._create_field_via_route(
            pool,
            redis_client,
            v5_field_route_client,
            field_route_actor,
        )

        response = await v5_field_route_client.client.post(
            "/v5/fields/export",
            json={"field_id": created["field_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] == 1

    async def test_field_refresh_route_returns_invalidated_tags(
        self,
        v5_field_route_client,
        field_route_actor,
    ):
        v5_field_route_client.authenticate(
            profile_id=field_route_actor.profile_id,
            session_id=field_route_actor.session_id,
        )

        response = await v5_field_route_client.client.post(
            "/v5/fields/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "fields,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["invalidated_tags"] == ["fields", "artifacts"]

    async def _create_field_via_route(
        self,
        pool,
        redis_client,
        v5_field_route_client,
        field_route_actor,
    ) -> dict[str, str]:
        resources = await _create_field_route_resources(pool, redis_client)
        v5_field_route_client.authenticate(
            profile_id=field_route_actor.profile_id,
            session_id=field_route_actor.session_id,
        )

        response = await v5_field_route_client.client.post(
            "/v5/fields/create",
            json={
                "fields": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(field_route_actor.department_id)],
                        "conditional_parameter_ids": [
                            str(resources.conditional_parameter_id)
                        ],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        return {
            "field_id": payload["results"][0]["field_id"],
            "name": resources.name,
            "description": resources.description,
        }
