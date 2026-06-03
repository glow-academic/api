"""End-to-end tests for the canonical document HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio

from tests.helpers import unique_tag
from tests.infra.route_helpers import (
    create_admin_route_actor,
    selected_resource,
    selected_resources,
)


@dataclass(frozen=True)
class DocumentRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str
    department_id: UUID
    department_name: str | None


async def _create_document_route_resources(
    pool, redis_client
) -> DocumentRouteResources:
    from app.tools.resources.departments.create import create_department
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.names.create import create_name

    tag = unique_tag()
    name = f"Route Document {tag}"
    description = f"Route document description {tag}"

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)
        department_res = await create_department(
            conn,
            name=f"Route Document Department {tag}",
            description=f"Document department {tag}",
            redis=redis_client,
        )

    return DocumentRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
        department_id=department_res.id,
        department_name=department_res.name,
    )


@pytest_asyncio.fixture
async def document_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["document", "scenario", "persona"],
        group_name="document-route",
        role_name_prefix="Document Route Admin",
    )


@pytest.mark.asyncio
class TestDocumentRoute:
    async def test_create_document_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        document_route_client,
        document_route_actor,
    ):
        resources = await _create_document_route_resources(pool, redis_client)
        document_route_client.authenticate(
            profile_id=document_route_actor.profile_id,
            session_id=document_route_actor.session_id,
        )

        response = await document_route_client.client.post(
            "/document/create",
            json={
                "documents": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(document_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "documents"

        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["message"] == "Document created successfully"
        assert payload["results"][0]["document_id"] is not None

    async def test_get_document_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        document_route_client,
        document_route_actor,
    ):
        created = await self._create_document_via_route(
            pool,
            redis_client,
            document_route_client,
            document_route_actor,
        )

        response = await document_route_client.client.post(
            "/document/get",
            json={"document_id": created["document_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "documents"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["actor_name"] == document_route_actor.name
        assert payload["document_exists"] is True
        assert payload["group_id"] is not None
        assert selected_resource(payload["names"])["name"] == created["name"]
        assert (
            selected_resource(payload["descriptions"])["description"]
            == created["description"]
        )
        assert {
            department["department_id"]
            for department in selected_resources(payload["departments"])
        } == {str(document_route_actor.department_id)}

    async def test_search_document_route_returns_created_document(
        self,
        pool,
        redis_client,
        document_route_client,
        document_route_actor,
    ):
        created = await self._create_document_via_route(
            pool,
            redis_client,
            document_route_client,
            document_route_actor,
        )

        response = await document_route_client.client.post(
            "/document/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(document_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "documents"

        payload = response.json()
        assert payload["actor_name"] == document_route_actor.name
        assert payload["total_count"] >= 1
        assert any(
            document["document_id"] == created["document_id"]
            for document in payload["documents"]
        )

    async def test_update_document_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        document_route_client,
        document_route_actor,
    ):
        created = await self._create_document_via_route(
            pool,
            redis_client,
            document_route_client,
            document_route_actor,
        )
        updated = await _create_document_route_resources(pool, redis_client)

        response = await document_route_client.client.post(
            "/document/update",
            json={
                "documents": [
                    {
                        "document_id": created["document_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "department_ids": [str(document_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "documents"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["document_id"] == created["document_id"]

        get_response = await document_route_client.client.post(
            "/document/get",
            json={"document_id": created["document_id"]},
            headers={"X-Bypass-Cache": "1"},
        )
        get_payload = get_response.json()
        assert selected_resource(get_payload["names"])["name"] == updated.name
        assert (
            selected_resource(get_payload["descriptions"])["description"]
            == updated.description
        )

    async def test_delete_document_route_soft_deletes_document(
        self,
        pool,
        redis_client,
        document_route_client,
        document_route_actor,
    ):
        created = await self._create_document_via_route(
            pool,
            redis_client,
            document_route_client,
            document_route_actor,
        )

        response = await document_route_client.client.post(
            "/document/delete",
            json={"document_ids": [created["document_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "documents"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["document_id"] == created["document_id"]

    async def test_duplicate_document_route_creates_new_document(
        self,
        pool,
        redis_client,
        document_route_client,
        document_route_actor,
    ):
        created = await self._create_document_via_route(
            pool,
            redis_client,
            document_route_client,
            document_route_actor,
        )

        response = await document_route_client.client.post(
            "/document/duplicate",
            json={"document_id": created["document_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "documents"
        payload = response.json()
        assert payload["success"] is True
        assert payload["document_id"] != created["document_id"]

    async def test_document_draft_route_creates_server_authoritative_draft(
        self,
        pool,
        redis_client,
        document_route_client,
        document_route_actor,
    ):
        resources = await _create_document_route_resources(pool, redis_client)
        document_route_client.authenticate(
            profile_id=document_route_actor.profile_id,
            session_id=document_route_actor.session_id,
        )

        response = await document_route_client.client.post(
            "/document/draft",
            json={
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(resources.department_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "documents,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["draft_id"] is not None
        assert payload["form_state"]["name_id"] == str(resources.name_id)

    async def test_document_drafts_route_lists_owned_drafts(
        self,
        pool,
        redis_client,
        document_route_client,
        document_route_actor,
    ):
        resources = await _create_document_route_resources(pool, redis_client)
        document_route_client.authenticate(
            profile_id=document_route_actor.profile_id,
            session_id=document_route_actor.session_id,
        )
        draft_response = await document_route_client.client.post(
            "/document/draft",
            json={
                "name_id": str(resources.name_id),
            },
        )
        assert draft_response.status_code == 200, draft_response.text

        response = await document_route_client.client.post(
            "/document/drafts",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "documents,drafts"
        payload = response.json()
        assert payload["entries"]
        assert any(
            entry["id"] == draft_response.json()["draft_id"]
            for entry in payload["entries"]
        )

    async def test_document_docs_route_returns_composed_docs(
        self,
        document_route_client,
        document_route_actor,
    ):
        document_route_client.authenticate(
            profile_id=document_route_actor.profile_id,
            session_id=document_route_actor.session_id,
        )

        response = await document_route_client.client.post(
            "/document/context",
            json={"entity_id": None, "schema": True},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "document"
        assert payload["type"] == "artifact"
        assert payload["page_metadata"]["list"]["title"] == "Documents"

    async def test_document_export_route_returns_csv_upload(
        self,
        pool,
        redis_client,
        document_route_client,
        document_route_actor,
    ):
        created = await self._create_document_via_route(
            pool,
            redis_client,
            document_route_client,
            document_route_actor,
        )

        response = await document_route_client.client.post(
            "/document/export",
            json={"document_id": created["document_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] >= 1

    async def test_document_refresh_route_returns_invalidated_tags(
        self,
        document_route_client,
        document_route_actor,
    ):
        document_route_client.authenticate(
            profile_id=document_route_actor.profile_id,
            session_id=document_route_actor.session_id,
        )

        response = await document_route_client.client.post(
            "/document/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "documents,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["refreshed_views"] == ["document_drafts_mv"]
        assert payload["invalidated_tags"] == ["documents", "artifacts"]

    async def _create_document_via_route(
        self,
        pool,
        redis_client,
        document_route_client,
        document_route_actor,
    ) -> dict[str, str]:
        resources = await _create_document_route_resources(pool, redis_client)
        document_route_client.authenticate(
            profile_id=document_route_actor.profile_id,
            session_id=document_route_actor.session_id,
        )

        response = await document_route_client.client.post(
            "/document/create",
            json={
                "documents": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(document_route_actor.department_id)],
                    }
                ]
            },
        )
        assert response.status_code == 200, response.text
        document_id = response.json()["results"][0]["document_id"]

        return {
            "document_id": document_id,
            "name": resources.name,
            "description": resources.description,
            "department_id": str(document_route_actor.department_id),
        }
