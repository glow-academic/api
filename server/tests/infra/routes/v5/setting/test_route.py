"""End-to-end tests for the canonical setting HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import create_admin_route_actor


@dataclass(frozen=True)
class SettingRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str


async def _create_setting_route_resources(pool, redis_client) -> SettingRouteResources:
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.names.create import create_name

    tag = unique_tag()
    name = f"Route Setting {tag}"
    description = f"Route setting description {tag}"

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)

    return SettingRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
    )


@pytest_asyncio.fixture
async def setting_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["setting", "system", "persona"],
        group_name="setting-route",
        role_name_prefix="Setting Route Admin",
    )


@pytest.mark.asyncio
class TestSettingRoute:
    async def test_create_setting_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        v5_setting_route_client,
        setting_route_actor,
    ):
        resources = await _create_setting_route_resources(pool, redis_client)
        v5_setting_route_client.authenticate(
            profile_id=setting_route_actor.profile_id,
            session_id=setting_route_actor.session_id,
        )

        response = await v5_setting_route_client.client.post(
            "/v5/settings/create",
            json={
                "settings": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(setting_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "settings"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["setting_id"] is not None

    async def test_get_setting_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        v5_setting_route_client,
        setting_route_actor,
    ):
        created = await self._create_setting_via_route(
            pool,
            redis_client,
            v5_setting_route_client,
            setting_route_actor,
        )

        response = await v5_setting_route_client.client.post(
            "/v5/settings/get",
            json={"settings_id": created["setting_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "settings"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["actor_name"] == setting_route_actor.name
        assert payload["setting_exists"] is True
        assert payload["group_id"] is not None
        assert payload["names"]["resource"]["name"] == created["name"]
        assert (
            payload["descriptions"]["resource"]["description"] == created["description"]
        )
        assert {item["id"] for item in payload["departments"]["current"]} == {
            str(setting_route_actor.department_id)
        }

    async def test_search_setting_route_returns_created_setting(
        self,
        pool,
        redis_client,
        v5_setting_route_client,
        setting_route_actor,
    ):
        created = await self._create_setting_via_route(
            pool,
            redis_client,
            v5_setting_route_client,
            setting_route_actor,
        )

        response = await v5_setting_route_client.client.post(
            "/v5/settings/search",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "settings"
        payload = response.json()
        assert payload["actor_name"] == setting_route_actor.name
        assert any(
            setting["settings_id"] == created["setting_id"]
            for setting in payload["settings"]
        )

    async def test_update_setting_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        v5_setting_route_client,
        setting_route_actor,
    ):
        created = await self._create_setting_via_route(
            pool,
            redis_client,
            v5_setting_route_client,
            setting_route_actor,
        )
        updated = await _create_setting_route_resources(pool, redis_client)

        response = await v5_setting_route_client.client.post(
            "/v5/settings/update",
            json={
                "settings": [
                    {
                        "setting_id": created["setting_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "department_ids": [str(setting_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "settings"
        payload = response.json()
        assert payload["results"][0]["success"] is True

        get_response = await v5_setting_route_client.client.post(
            "/v5/settings/get",
            json={"settings_id": created["setting_id"]},
            headers={"X-Bypass-Cache": "1"},
        )
        get_payload = get_response.json()
        assert get_payload["names"]["resource"]["name"] == updated.name
        assert (
            get_payload["descriptions"]["resource"]["description"]
            == updated.description
        )

    async def test_delete_setting_route_soft_deletes_setting(
        self,
        pool,
        redis_client,
        v5_setting_route_client,
        setting_route_actor,
    ):
        created = await self._create_setting_via_route(
            pool,
            redis_client,
            v5_setting_route_client,
            setting_route_actor,
        )

        response = await v5_setting_route_client.client.post(
            "/v5/settings/delete",
            json={"setting_ids": [created["setting_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "settings"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_duplicate_setting_route_creates_new_setting(
        self,
        pool,
        redis_client,
        v5_setting_route_client,
        setting_route_actor,
    ):
        created = await self._create_setting_via_route(
            pool,
            redis_client,
            v5_setting_route_client,
            setting_route_actor,
        )

        response = await v5_setting_route_client.client.post(
            "/v5/settings/duplicate",
            json={"setting_id": created["setting_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "settings"
        payload = response.json()
        assert payload["success"] is True
        assert payload["setting_id"] != created["setting_id"]

    async def test_setting_draft_route_creates_server_authoritative_draft(
        self,
        pool,
        redis_client,
        v5_setting_route_client,
        setting_route_actor,
    ):
        resources = await _create_setting_route_resources(pool, redis_client)
        v5_setting_route_client.authenticate(
            profile_id=setting_route_actor.profile_id,
            session_id=setting_route_actor.session_id,
        )

        response = await v5_setting_route_client.client.patch(
            "/v5/settings/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(setting_route_actor.department_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "settings,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["new_version"] == 1
        assert payload["form_state"]["name_id"] == str(resources.name_id)

    async def test_setting_drafts_route_lists_owned_drafts(
        self,
        pool,
        redis_client,
        v5_setting_route_client,
        setting_route_actor,
    ):
        resources = await _create_setting_route_resources(pool, redis_client)
        v5_setting_route_client.authenticate(
            profile_id=setting_route_actor.profile_id,
            session_id=setting_route_actor.session_id,
        )
        draft_response = await v5_setting_route_client.client.patch(
            "/v5/settings/draft",
            json={"expected_version": 0, "name_id": str(resources.name_id)},
        )
        assert draft_response.status_code == 200, draft_response.text

        response = await v5_setting_route_client.client.post(
            "/v5/settings/drafts",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "settings,drafts"
        payload = response.json()
        assert payload["entries"]

    async def test_setting_docs_route_returns_composed_docs(
        self,
        v5_setting_route_client,
        setting_route_actor,
    ):
        v5_setting_route_client.authenticate(
            profile_id=setting_route_actor.profile_id,
            session_id=setting_route_actor.session_id,
        )

        response = await v5_setting_route_client.client.post(
            "/v5/settings/docs",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "setting"
        assert payload["type"] == "artifact"
        assert payload["entries"]
        assert payload["page_metadata"]["list"]["title"] == "Settings"

    async def test_setting_export_route_returns_csv_upload(
        self,
        pool,
        redis_client,
        v5_setting_route_client,
        setting_route_actor,
    ):
        created = await self._create_setting_via_route(
            pool,
            redis_client,
            v5_setting_route_client,
            setting_route_actor,
        )

        response = await v5_setting_route_client.client.post(
            "/v5/settings/export",
            json={"setting_id": created["setting_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] >= 1

    async def test_setting_refresh_route_returns_invalidated_tags(
        self,
        v5_setting_route_client,
        setting_route_actor,
    ):
        v5_setting_route_client.authenticate(
            profile_id=setting_route_actor.profile_id,
            session_id=setting_route_actor.session_id,
        )

        response = await v5_setting_route_client.client.post(
            "/v5/settings/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "settings,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert set(payload["invalidated_tags"]) == {"settings", "artifacts"}

    async def test_setting_decrypt_route_rejects_key_outside_setting_scope(
        self,
        pool,
        redis_client,
        v5_setting_route_client,
        setting_route_actor,
    ):
        created = await self._create_setting_via_route(
            pool,
            redis_client,
            v5_setting_route_client,
            setting_route_actor,
        )
        v5_setting_route_client.authenticate(
            profile_id=setting_route_actor.profile_id,
            session_id=setting_route_actor.session_id,
        )

        response = await v5_setting_route_client.client.post(
            "/v5/settings/decrypt",
            json={
                "setting_id": created["setting_id"],
                "key_id": str(uuid4()),
            },
        )

        assert response.status_code == 403, response.text
        assert response.json()["detail"] == "Key does not belong to this setting"

    async def _create_setting_via_route(
        self,
        pool,
        redis_client,
        v5_setting_route_client,
        setting_route_actor,
    ) -> dict[str, str]:
        resources = await _create_setting_route_resources(pool, redis_client)
        v5_setting_route_client.authenticate(
            profile_id=setting_route_actor.profile_id,
            session_id=setting_route_actor.session_id,
        )

        response = await v5_setting_route_client.client.post(
            "/v5/settings/create",
            json={
                "settings": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(setting_route_actor.department_id)],
                    }
                ]
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        return {
            "setting_id": payload["results"][0]["setting_id"],
            "name": resources.name,
            "description": resources.description,
        }
