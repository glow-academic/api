"""End-to-end tests for the canonical provider HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import create_admin_route_actor

from app.utils.auth.encrypt_api_key import encrypt_api_key


@dataclass(frozen=True)
class ProviderRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str
    department_id: UUID
    endpoint_id: UUID
    key_id: UUID
    decrypted_key: str
    value_id: UUID


async def _create_provider_route_resources(
    pool, redis_client
) -> ProviderRouteResources:
    from app.tools.resources.departments.create import create_department
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.endpoints.create import create_endpoint
    from app.tools.resources.keys.create import create_key
    from app.tools.resources.names.create import create_name
    from app.tools.resources.values.create import create_value

    tag = unique_tag()
    name = f"Route Provider {tag}"
    description = f"Route provider description {tag}"
    raw_key = f"sk-route-{tag}"

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)
        department_res = await create_department(conn, redis=redis_client)
        endpoint_res = await create_endpoint(
            conn,
            f"https://provider-{tag}.example.com",
            redis_client,
        )
        key_res = await create_key(
            conn,
            redis_client,
            name=f"Route Key {tag}",
            description=f"Route key description {tag}",
            key=encrypt_api_key(raw_key),
        )
        value_res = await create_value(
            conn,
            f"provider-value-{tag}",
            redis_client,
        )

    return ProviderRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
        department_id=department_res.id,
        endpoint_id=endpoint_res.id,
        key_id=key_res.id,
        decrypted_key=raw_key,
        value_id=value_res.id,
    )


@pytest_asyncio.fixture
async def provider_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["provider", "agent", "persona"],
        group_name="provider-route",
        role_name_prefix="Provider Route Admin",
    )


@pytest.mark.asyncio
class TestProviderRoute:
    async def test_create_provider_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        v5_provider_route_client,
        provider_route_actor,
    ):
        resources = await _create_provider_route_resources(pool, redis_client)
        v5_provider_route_client.authenticate(
            profile_id=provider_route_actor.profile_id,
            session_id=provider_route_actor.session_id,
        )

        response = await v5_provider_route_client.client.post(
            "/v5/providers/create",
            json={
                "providers": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(provider_route_actor.department_id)],
                        "endpoint_ids": [str(resources.endpoint_id)],
                        "key_ids": [str(resources.key_id)],
                        "value_ids": [str(resources.value_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "providers"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["provider_id"] is not None

    async def test_get_provider_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        v5_provider_route_client,
        provider_route_actor,
    ):
        created = await self._create_provider_via_route(
            pool,
            redis_client,
            v5_provider_route_client,
            provider_route_actor,
        )

        response = await v5_provider_route_client.client.post(
            "/v5/providers/get",
            json={"provider_id": created["provider_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "providers"
        payload = response.json()
        assert payload["actor_name"] == provider_route_actor.name
        assert payload["provider_exists"] is True
        assert payload["group_id"] is not None
        assert payload["names"]["resource"]["name"] == created["name"]
        assert (
            payload["descriptions"]["resource"]["description"] == created["description"]
        )

    async def test_search_provider_route_returns_created_provider(
        self,
        pool,
        redis_client,
        v5_provider_route_client,
        provider_route_actor,
    ):
        created = await self._create_provider_via_route(
            pool,
            redis_client,
            v5_provider_route_client,
            provider_route_actor,
        )

        response = await v5_provider_route_client.client.post(
            "/v5/providers/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(provider_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "providers"
        payload = response.json()
        assert payload["actor_name"] == provider_route_actor.name
        assert payload["total_count"] >= 1
        assert any(
            provider["provider_id"] == created["provider_id"]
            for provider in payload["providers"]
        )

    async def test_update_provider_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        v5_provider_route_client,
        provider_route_actor,
    ):
        created = await self._create_provider_via_route(
            pool,
            redis_client,
            v5_provider_route_client,
            provider_route_actor,
        )
        updated = await _create_provider_route_resources(pool, redis_client)

        response = await v5_provider_route_client.client.post(
            "/v5/providers/update",
            json={
                "providers": [
                    {
                        "provider_id": created["provider_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "department_ids": [str(provider_route_actor.department_id)],
                        "endpoint_ids": [str(updated.endpoint_id)],
                        "key_ids": [str(updated.key_id)],
                        "value_ids": [str(updated.value_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "providers"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_delete_provider_route_soft_deletes_provider(
        self,
        pool,
        redis_client,
        v5_provider_route_client,
        provider_route_actor,
    ):
        created = await self._create_provider_via_route(
            pool,
            redis_client,
            v5_provider_route_client,
            provider_route_actor,
        )

        response = await v5_provider_route_client.client.post(
            "/v5/providers/delete",
            json={"provider_ids": [created["provider_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "providers"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_duplicate_provider_route_creates_new_provider(
        self,
        pool,
        redis_client,
        v5_provider_route_client,
        provider_route_actor,
    ):
        created = await self._create_provider_via_route(
            pool,
            redis_client,
            v5_provider_route_client,
            provider_route_actor,
        )

        response = await v5_provider_route_client.client.post(
            "/v5/providers/duplicate",
            json={"provider_id": created["provider_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "providers"
        payload = response.json()
        assert payload["success"] is True
        assert payload["provider_id"] != created["provider_id"]

    async def test_provider_draft_route_creates_server_authoritative_draft(
        self,
        pool,
        redis_client,
        v5_provider_route_client,
        provider_route_actor,
    ):
        resources = await _create_provider_route_resources(pool, redis_client)
        v5_provider_route_client.authenticate(
            profile_id=provider_route_actor.profile_id,
            session_id=provider_route_actor.session_id,
        )

        response = await v5_provider_route_client.client.patch(
            "/v5/providers/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(provider_route_actor.department_id)],
                "endpoint_ids": [str(resources.endpoint_id)],
                "key_ids": [str(resources.key_id)],
                "value_ids": [str(resources.value_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "providers,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["draft_id"] is not None
        assert payload["new_version"] == 1
        assert payload["form_state"]["name_id"] == str(resources.name_id)

    async def test_provider_drafts_route_lists_owned_drafts(
        self,
        pool,
        redis_client,
        v5_provider_route_client,
        provider_route_actor,
    ):
        resources = await _create_provider_route_resources(pool, redis_client)
        v5_provider_route_client.authenticate(
            profile_id=provider_route_actor.profile_id,
            session_id=provider_route_actor.session_id,
        )

        draft_response = await v5_provider_route_client.client.patch(
            "/v5/providers/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(provider_route_actor.department_id)],
            },
        )
        assert draft_response.status_code == 200, draft_response.text
        draft_id = draft_response.json()["draft_id"]

        response = await v5_provider_route_client.client.post(
            "/v5/providers/drafts",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "providers,drafts"
        payload = response.json()
        assert any(entry["id"] == draft_id for entry in (payload["entries"] or []))

    async def test_provider_docs_route_returns_composed_docs(
        self,
        v5_provider_route_client,
        provider_route_actor,
    ):
        v5_provider_route_client.authenticate(
            profile_id=provider_route_actor.profile_id,
            session_id=provider_route_actor.session_id,
        )

        response = await v5_provider_route_client.client.post(
            "/v5/providers/docs",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "provider"
        assert payload["type"] == "artifact"
        assert payload["artifact"] is not None
        assert payload["api_operations"]

    async def test_provider_export_route_returns_csv_upload(
        self,
        pool,
        redis_client,
        v5_provider_route_client,
        provider_route_actor,
    ):
        created = await self._create_provider_via_route(
            pool,
            redis_client,
            v5_provider_route_client,
            provider_route_actor,
        )

        response = await v5_provider_route_client.client.post(
            "/v5/providers/export",
            json={"provider_id": created["provider_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] == 1

    async def test_provider_refresh_route_returns_invalidated_tags(
        self,
        v5_provider_route_client,
        provider_route_actor,
    ):
        v5_provider_route_client.authenticate(
            profile_id=provider_route_actor.profile_id,
            session_id=provider_route_actor.session_id,
        )

        response = await v5_provider_route_client.client.post(
            "/v5/providers/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "providers,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["invalidated_tags"] == ["providers", "artifacts"]

    async def test_provider_decrypt_route_returns_decrypted_key(
        self,
        pool,
        redis_client,
        v5_provider_route_client,
        provider_route_actor,
    ):
        created = await self._create_provider_via_route(
            pool,
            redis_client,
            v5_provider_route_client,
            provider_route_actor,
        )

        response = await v5_provider_route_client.client.post(
            "/v5/providers/decrypt",
            json={
                "provider_id": created["provider_id"],
                "key_id": created["key_id"],
            },
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["key"] == created["decrypted_key"]
        assert payload["name"] is not None
        assert payload["actor_name"] == provider_route_actor.name

    async def _create_provider_via_route(
        self,
        pool,
        redis_client,
        v5_provider_route_client,
        provider_route_actor,
    ) -> dict[str, str]:
        resources = await _create_provider_route_resources(pool, redis_client)
        v5_provider_route_client.authenticate(
            profile_id=provider_route_actor.profile_id,
            session_id=provider_route_actor.session_id,
        )

        response = await v5_provider_route_client.client.post(
            "/v5/providers/create",
            json={
                "providers": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(provider_route_actor.department_id)],
                        "endpoint_ids": [str(resources.endpoint_id)],
                        "key_ids": [str(resources.key_id)],
                        "value_ids": [str(resources.value_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        return {
            "provider_id": payload["results"][0]["provider_id"],
            "name": resources.name,
            "description": resources.description,
            "key_id": str(resources.key_id),
            "decrypted_key": resources.decrypted_key,
        }
