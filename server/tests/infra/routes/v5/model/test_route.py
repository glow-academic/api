"""End-to-end tests for the canonical model HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import create_admin_route_actor


@dataclass(frozen=True)
class ModelRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str


async def _create_model_route_resources(pool, redis_client) -> ModelRouteResources:
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.names.create import create_name

    tag = unique_tag()
    name = f"Route Model {tag}"
    description = f"Route model description {tag}"

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)

    return ModelRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
    )


@pytest_asyncio.fixture
async def model_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["model", "agent", "persona"],
        group_name="model-route",
        role_name_prefix="Model Route Admin",
    )


@pytest.mark.asyncio
class TestModelRoute:
    async def test_create_model_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        v5_model_route_client,
        model_route_actor,
    ):
        resources = await _create_model_route_resources(pool, redis_client)
        v5_model_route_client.authenticate(
            profile_id=model_route_actor.profile_id,
            session_id=model_route_actor.session_id,
        )

        response = await v5_model_route_client.client.post(
            "/v5/models/create",
            json={
                "models": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(model_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "models"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["model_id"] is not None

    async def test_get_model_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        v5_model_route_client,
        model_route_actor,
    ):
        created = await self._create_model_via_route(
            pool,
            redis_client,
            v5_model_route_client,
            model_route_actor,
        )

        response = await v5_model_route_client.client.post(
            "/v5/models/get",
            json={"model_id": created["model_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "models"
        assert response.headers["X-Cache-Hit"] == "0"
        payload = response.json()
        assert payload["actor_name"] == model_route_actor.name
        assert payload["model_exists"] is True
        assert payload["group_id"] is not None
        assert payload["names"]["resource"]["name"] == created["name"]
        assert (
            payload["descriptions"]["resource"]["description"] == created["description"]
        )

    async def test_search_model_route_returns_created_model(
        self,
        pool,
        redis_client,
        v5_model_route_client,
        model_route_actor,
    ):
        created = await self._create_model_via_route(
            pool,
            redis_client,
            v5_model_route_client,
            model_route_actor,
        )

        response = await v5_model_route_client.client.post(
            "/v5/models/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(model_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "models"
        payload = response.json()
        assert payload["actor_name"] == model_route_actor.name
        assert payload["total_count"] >= 1
        assert any(
            model["model_id"] == created["model_id"] for model in payload["models"]
        )

    async def test_update_model_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        v5_model_route_client,
        model_route_actor,
    ):
        created = await self._create_model_via_route(
            pool,
            redis_client,
            v5_model_route_client,
            model_route_actor,
        )
        updated = await _create_model_route_resources(pool, redis_client)

        response = await v5_model_route_client.client.post(
            "/v5/models/update",
            json={
                "models": [
                    {
                        "model_id": created["model_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "department_ids": [str(model_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "models"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_delete_model_route_soft_deletes_model(
        self,
        pool,
        redis_client,
        v5_model_route_client,
        model_route_actor,
    ):
        created = await self._create_model_via_route(
            pool,
            redis_client,
            v5_model_route_client,
            model_route_actor,
        )

        response = await v5_model_route_client.client.post(
            "/v5/models/delete",
            json={"model_ids": [created["model_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "models"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_duplicate_model_route_creates_new_model(
        self,
        pool,
        redis_client,
        v5_model_route_client,
        model_route_actor,
    ):
        created = await self._create_model_via_route(
            pool,
            redis_client,
            v5_model_route_client,
            model_route_actor,
        )

        response = await v5_model_route_client.client.post(
            "/v5/models/duplicate",
            json={"model_id": created["model_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "models"
        payload = response.json()
        assert payload["success"] is True
        assert payload["model_id"] != created["model_id"]

    async def test_model_draft_route_creates_server_authoritative_draft(
        self,
        pool,
        redis_client,
        v5_model_route_client,
        model_route_actor,
    ):
        resources = await _create_model_route_resources(pool, redis_client)
        v5_model_route_client.authenticate(
            profile_id=model_route_actor.profile_id,
            session_id=model_route_actor.session_id,
        )

        response = await v5_model_route_client.client.patch(
            "/v5/models/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(model_route_actor.department_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "models,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["new_version"] == 1

    async def test_model_drafts_route_lists_owned_drafts(
        self,
        pool,
        redis_client,
        v5_model_route_client,
        model_route_actor,
    ):
        resources = await _create_model_route_resources(pool, redis_client)
        v5_model_route_client.authenticate(
            profile_id=model_route_actor.profile_id,
            session_id=model_route_actor.session_id,
        )
        draft_response = await v5_model_route_client.client.patch(
            "/v5/models/draft",
            json={"expected_version": 0, "name_id": str(resources.name_id)},
        )
        assert draft_response.status_code == 200, draft_response.text

        response = await v5_model_route_client.client.post(
            "/v5/models/drafts",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "models,drafts"
        payload = response.json()
        assert payload["entries"]

    async def test_model_docs_route_returns_composed_docs(
        self,
        v5_model_route_client,
        model_route_actor,
    ):
        v5_model_route_client.authenticate(
            profile_id=model_route_actor.profile_id,
            session_id=model_route_actor.session_id,
        )

        response = await v5_model_route_client.client.post(
            "/v5/models/docs",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "model"
        assert payload["type"] == "artifact"
        assert payload["entries"]
        assert payload["page_metadata"]["list"]["title"] == "Models"

    async def test_model_export_route_returns_csv_upload(
        self,
        pool,
        redis_client,
        v5_model_route_client,
        model_route_actor,
    ):
        created = await self._create_model_via_route(
            pool,
            redis_client,
            v5_model_route_client,
            model_route_actor,
        )

        response = await v5_model_route_client.client.post(
            "/v5/models/export",
            json={"model_id": created["model_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] >= 1

    async def test_model_refresh_route_returns_invalidated_tags(
        self,
        v5_model_route_client,
        model_route_actor,
    ):
        v5_model_route_client.authenticate(
            profile_id=model_route_actor.profile_id,
            session_id=model_route_actor.session_id,
        )

        response = await v5_model_route_client.client.post(
            "/v5/models/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "models,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert set(payload["invalidated_tags"]) == {"models", "artifacts"}

    async def _create_model_via_route(
        self,
        pool,
        redis_client,
        v5_model_route_client,
        model_route_actor,
    ) -> dict[str, str]:
        resources = await _create_model_route_resources(pool, redis_client)
        v5_model_route_client.authenticate(
            profile_id=model_route_actor.profile_id,
            session_id=model_route_actor.session_id,
        )

        response = await v5_model_route_client.client.post(
            "/v5/models/create",
            json={
                "models": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(model_route_actor.department_id)],
                    }
                ]
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        return {
            "model_id": payload["results"][0]["model_id"],
            "name": resources.name,
            "description": resources.description,
        }
