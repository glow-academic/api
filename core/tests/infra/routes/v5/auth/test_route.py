"""End-to-end tests for the canonical auth HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import create_admin_route_actor


@dataclass(frozen=True)
class AuthRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str
    protocol_id: UUID
    slug_id: UUID
    item_id: UUID


async def _create_auth_route_resources(pool, redis_client) -> AuthRouteResources:
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.items.create import create_item
    from app.tools.resources.names.create import create_name
    from app.tools.resources.protocols.create import create_protocol
    from app.tools.resources.slugs.create import create_slug

    tag = unique_tag()
    name = f"Route Auth {tag}"
    description = f"Route auth description {tag}"

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)
        protocol_res = await create_protocol(
            conn, f"route-protocol-{tag}", redis_client
        )
        slug_res = await create_slug(conn, f"route-auth-{tag}", redis_client)
        item_res = await create_item(
            conn,
            f"Route Auth Item {tag}",
            f"Route auth item description {tag}",
            redis_client,
        )

    return AuthRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
        protocol_id=protocol_res.id,
        slug_id=slug_res.id,
        item_id=item_res.id,
    )


@pytest_asyncio.fixture
async def auth_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["auth", "agent", "persona"],
        group_name="auth-route",
        role_name_prefix="Auth Route Admin",
        role="superadmin",
    )


@pytest.mark.asyncio
class TestAuthRoute:
    async def test_create_auth_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        v5_auth_route_client,
        auth_route_actor,
    ):
        resources = await _create_auth_route_resources(pool, redis_client)
        v5_auth_route_client.authenticate(
            profile_id=auth_route_actor.profile_id,
            session_id=auth_route_actor.session_id,
        )

        response = await v5_auth_route_client.client.post(
            "/v5/auths/create",
            json={
                "auths": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(auth_route_actor.department_id)],
                        "protocol_ids": [str(resources.protocol_id)],
                        "slug_id": str(resources.slug_id),
                        "item_ids": [str(resources.item_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "auths"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["auth_id"] is not None

    async def test_get_auth_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        v5_auth_route_client,
        auth_route_actor,
    ):
        created = await self._create_auth_via_route(
            pool,
            redis_client,
            v5_auth_route_client,
            auth_route_actor,
        )

        response = await v5_auth_route_client.client.post(
            "/v5/auths/get",
            json={"auth_id": created["auth_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "auths"
        payload = response.json()
        assert payload["actor_name"] == auth_route_actor.name
        assert payload["auth_exists"] is True
        assert payload["group_id"] is not None
        assert payload["names"]["resource"]["name"] == created["name"]
        assert (
            payload["descriptions"]["resource"]["description"] == created["description"]
        )

    async def test_search_auth_route_returns_created_auth(
        self,
        pool,
        redis_client,
        v5_auth_route_client,
        auth_route_actor,
    ):
        created = await self._create_auth_via_route(
            pool,
            redis_client,
            v5_auth_route_client,
            auth_route_actor,
        )

        response = await v5_auth_route_client.client.post(
            "/v5/auths/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(auth_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "auths"
        payload = response.json()
        assert payload["actor_name"] == auth_route_actor.name
        assert payload["total_count"] >= 1
        assert any(
            auth_item["auth_id"] == created["auth_id"] for auth_item in payload["auths"]
        )

    async def test_update_auth_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        v5_auth_route_client,
        auth_route_actor,
    ):
        created = await self._create_auth_via_route(
            pool,
            redis_client,
            v5_auth_route_client,
            auth_route_actor,
        )
        updated = await _create_auth_route_resources(pool, redis_client)

        response = await v5_auth_route_client.client.post(
            "/v5/auths/update",
            json={
                "auths": [
                    {
                        "auth_id": created["auth_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "department_ids": [str(auth_route_actor.department_id)],
                        "protocol_ids": [str(updated.protocol_id)],
                        "slug_id": str(updated.slug_id),
                        "item_ids": [str(updated.item_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "auths"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_delete_auth_route_soft_deletes_auth(
        self,
        pool,
        redis_client,
        v5_auth_route_client,
        auth_route_actor,
    ):
        created = await self._create_auth_via_route(
            pool,
            redis_client,
            v5_auth_route_client,
            auth_route_actor,
        )

        response = await v5_auth_route_client.client.post(
            "/v5/auths/delete",
            json={"auth_ids": [created["auth_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "auths"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_duplicate_auth_route_creates_new_auth(
        self,
        pool,
        redis_client,
        v5_auth_route_client,
        auth_route_actor,
    ):
        created = await self._create_auth_via_route(
            pool,
            redis_client,
            v5_auth_route_client,
            auth_route_actor,
        )

        response = await v5_auth_route_client.client.post(
            "/v5/auths/duplicate",
            json={"auth_id": created["auth_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "auths"
        payload = response.json()
        assert payload["success"] is True
        assert payload["auth_id"] != created["auth_id"]

    async def test_auth_draft_route_creates_server_authoritative_draft(
        self,
        pool,
        redis_client,
        v5_auth_route_client,
        auth_route_actor,
    ):
        resources = await _create_auth_route_resources(pool, redis_client)
        v5_auth_route_client.authenticate(
            profile_id=auth_route_actor.profile_id,
            session_id=auth_route_actor.session_id,
        )

        response = await v5_auth_route_client.client.patch(
            "/v5/auths/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(auth_route_actor.department_id)],
                "protocol_ids": [str(resources.protocol_id)],
                "slug_ids": [str(resources.slug_id)],
                "item_ids": [str(resources.item_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "auths,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["draft_id"] is not None
        assert payload["new_version"] == 1
        assert payload["form_state"]["name_id"] == str(resources.name_id)

    async def test_auth_drafts_route_lists_owned_drafts(
        self,
        pool,
        redis_client,
        v5_auth_route_client,
        auth_route_actor,
    ):
        resources = await _create_auth_route_resources(pool, redis_client)
        v5_auth_route_client.authenticate(
            profile_id=auth_route_actor.profile_id,
            session_id=auth_route_actor.session_id,
        )

        draft_response = await v5_auth_route_client.client.patch(
            "/v5/auths/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(auth_route_actor.department_id)],
                "protocol_ids": [str(resources.protocol_id)],
                "slug_ids": [str(resources.slug_id)],
                "item_ids": [str(resources.item_id)],
            },
        )
        assert draft_response.status_code == 200, draft_response.text
        draft_id = draft_response.json()["draft_id"]

        response = await v5_auth_route_client.client.post(
            "/v5/auths/drafts",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "auths,drafts"
        payload = response.json()
        assert any(entry["id"] == draft_id for entry in (payload["entries"] or []))

    async def test_auth_docs_route_returns_composed_docs(
        self,
        v5_auth_route_client,
        auth_route_actor,
    ):
        v5_auth_route_client.authenticate(
            profile_id=auth_route_actor.profile_id,
            session_id=auth_route_actor.session_id,
        )

        response = await v5_auth_route_client.client.post(
            "/v5/auths/docs",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "auth"
        assert payload["type"] == "artifact"
        assert payload["artifact"] is not None
        assert payload["api_operations"]

    async def test_auth_export_route_returns_csv_upload(
        self,
        pool,
        redis_client,
        v5_auth_route_client,
        auth_route_actor,
    ):
        created = await self._create_auth_via_route(
            pool,
            redis_client,
            v5_auth_route_client,
            auth_route_actor,
        )

        response = await v5_auth_route_client.client.post(
            "/v5/auths/export",
            json={"auth_id": created["auth_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] == 1

    async def test_auth_refresh_route_returns_invalidated_tags(
        self,
        v5_auth_route_client,
        auth_route_actor,
    ):
        v5_auth_route_client.authenticate(
            profile_id=auth_route_actor.profile_id,
            session_id=auth_route_actor.session_id,
        )

        response = await v5_auth_route_client.client.post(
            "/v5/auths/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "auths,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["invalidated_tags"] == ["auths", "artifacts"]

    async def _create_auth_via_route(
        self,
        pool,
        redis_client,
        v5_auth_route_client,
        auth_route_actor,
    ) -> dict[str, str]:
        resources = await _create_auth_route_resources(pool, redis_client)
        v5_auth_route_client.authenticate(
            profile_id=auth_route_actor.profile_id,
            session_id=auth_route_actor.session_id,
        )

        response = await v5_auth_route_client.client.post(
            "/v5/auths/create",
            json={
                "auths": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(auth_route_actor.department_id)],
                        "protocol_ids": [str(resources.protocol_id)],
                        "slug_id": str(resources.slug_id),
                        "item_ids": [str(resources.item_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        return {
            "auth_id": payload["results"][0]["auth_id"],
            "name": resources.name,
            "description": resources.description,
        }
