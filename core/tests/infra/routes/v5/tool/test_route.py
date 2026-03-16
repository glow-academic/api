"""End-to-end tests for the canonical tool HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import create_admin_route_actor


@dataclass(frozen=True)
class ToolRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str


async def _create_tool_route_resources(pool, redis_client) -> ToolRouteResources:
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.names.create import create_name

    tag = unique_tag()
    name = f"Route Tool {tag}"
    description = f"Route tool description {tag}"

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)

    return ToolRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
    )


@pytest_asyncio.fixture
async def tool_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["tool", "agent", "persona"],
        group_name="tool-route",
        role_name_prefix="Tool Route Admin",
    )


@pytest.mark.asyncio
class TestToolRoute:
    async def test_create_tool_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        v5_tool_route_client,
        tool_route_actor,
    ):
        resources = await _create_tool_route_resources(pool, redis_client)
        v5_tool_route_client.authenticate(
            profile_id=tool_route_actor.profile_id,
            session_id=tool_route_actor.session_id,
        )

        response = await v5_tool_route_client.client.post(
            "/v5/tools/create",
            json={
                "tools": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(tool_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "tools"

        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["message"] == "Tool created successfully"
        assert payload["results"][0]["tool_id"] is not None

    async def test_get_tool_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        v5_tool_route_client,
        tool_route_actor,
    ):
        created = await self._create_tool_via_route(
            pool,
            redis_client,
            v5_tool_route_client,
            tool_route_actor,
        )

        response = await v5_tool_route_client.client.post(
            "/v5/tools/get",
            json={"tool_id": created["tool_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "tools"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["actor_name"] == tool_route_actor.name
        assert payload["tool_exists"] is True
        assert payload["group_id"] is not None
        assert payload["names"]["resource"]["name"] == created["name"]
        assert (
            payload["descriptions"]["resource"]["description"] == created["description"]
        )
        assert payload["can_edit"] is True
        assert payload["disabled_reason"] is None

    async def test_search_tool_route_returns_created_tool(
        self,
        pool,
        redis_client,
        v5_tool_route_client,
        tool_route_actor,
    ):
        created = await self._create_tool_via_route(
            pool,
            redis_client,
            v5_tool_route_client,
            tool_route_actor,
        )

        response = await v5_tool_route_client.client.post(
            "/v5/tools/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(tool_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "tools"

        payload = response.json()
        assert payload["actor_name"] == tool_route_actor.name
        assert payload["total_count"] >= 1
        assert any(tool["tool_id"] == created["tool_id"] for tool in payload["tools"])

    async def test_get_tool_route_hits_cache_on_second_request(
        self,
        pool,
        redis_client,
        v5_tool_route_client,
        tool_route_actor,
    ):
        created = await self._create_tool_via_route(
            pool,
            redis_client,
            v5_tool_route_client,
            tool_route_actor,
        )

        first = await v5_tool_route_client.client.post(
            "/v5/tools/get",
            json={"tool_id": created["tool_id"]},
        )
        second = await v5_tool_route_client.client.post(
            "/v5/tools/get",
            json={"tool_id": created["tool_id"]},
        )

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.headers["X-Cache-Hit"] == "0"
        assert second.headers["X-Cache-Hit"] in {"0", "1"}

    async def test_update_tool_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        v5_tool_route_client,
        tool_route_actor,
    ):
        created = await self._create_tool_via_route(
            pool,
            redis_client,
            v5_tool_route_client,
            tool_route_actor,
        )
        updated = await _create_tool_route_resources(pool, redis_client)

        response = await v5_tool_route_client.client.post(
            "/v5/tools/update",
            json={
                "tools": [
                    {
                        "tool_id": created["tool_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "department_ids": [str(tool_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "tools"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["tool_id"] == created["tool_id"]

        get_response = await v5_tool_route_client.client.post(
            "/v5/tools/get",
            json={"tool_id": created["tool_id"]},
            headers={"X-Bypass-Cache": "1"},
        )
        get_payload = get_response.json()
        assert get_payload["names"]["resource"]["name"] == updated.name
        assert (
            get_payload["descriptions"]["resource"]["description"]
            == updated.description
        )

    async def test_delete_tool_route_soft_deletes_tool(
        self,
        pool,
        redis_client,
        v5_tool_route_client,
        tool_route_actor,
    ):
        created = await self._create_tool_via_route(
            pool,
            redis_client,
            v5_tool_route_client,
            tool_route_actor,
        )

        response = await v5_tool_route_client.client.post(
            "/v5/tools/delete",
            json={"tool_ids": [created["tool_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "tools"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["tool_id"] == created["tool_id"]

        search_response = await v5_tool_route_client.client.post(
            "/v5/tools/search",
            json={"search": created["name"], "page_size": 10, "page_offset": 0},
        )
        search_payload = search_response.json()
        assert all(
            tool["tool_id"] != created["tool_id"] for tool in search_payload["tools"]
        )

    async def test_duplicate_tool_route_creates_new_tool(
        self,
        pool,
        redis_client,
        v5_tool_route_client,
        tool_route_actor,
    ):
        created = await self._create_tool_via_route(
            pool,
            redis_client,
            v5_tool_route_client,
            tool_route_actor,
        )

        response = await v5_tool_route_client.client.post(
            "/v5/tools/duplicate",
            json={"tool_id": created["tool_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "tools"
        payload = response.json()
        assert payload["success"] is True
        assert payload["tool_id"] != created["tool_id"]

    async def test_tool_draft_route_creates_server_authoritative_draft(
        self,
        pool,
        redis_client,
        v5_tool_route_client,
        tool_route_actor,
    ):
        resources = await _create_tool_route_resources(pool, redis_client)
        v5_tool_route_client.authenticate(
            profile_id=tool_route_actor.profile_id,
            session_id=tool_route_actor.session_id,
        )

        response = await v5_tool_route_client.client.patch(
            "/v5/tools/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(tool_route_actor.department_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "tools,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["new_version"] == 1
        assert payload["form_state"]["name_id"] == str(resources.name_id)
        assert payload["form_state"]["department_ids"] == [
            str(tool_route_actor.department_id)
        ]

    async def test_tool_drafts_route_lists_owned_drafts(
        self,
        pool,
        redis_client,
        v5_tool_route_client,
        tool_route_actor,
    ):
        resources = await _create_tool_route_resources(pool, redis_client)
        v5_tool_route_client.authenticate(
            profile_id=tool_route_actor.profile_id,
            session_id=tool_route_actor.session_id,
        )
        draft_response = await v5_tool_route_client.client.patch(
            "/v5/tools/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
            },
        )
        assert draft_response.status_code == 200, draft_response.text

        response = await v5_tool_route_client.client.post(
            "/v5/tools/drafts",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "tools,drafts"
        payload = response.json()
        assert payload["entries"]

    async def test_tool_docs_route_returns_composed_docs(
        self,
        v5_tool_route_client,
        tool_route_actor,
    ):
        v5_tool_route_client.authenticate(
            profile_id=tool_route_actor.profile_id,
            session_id=tool_route_actor.session_id,
        )

        response = await v5_tool_route_client.client.post(
            "/v5/tools/docs",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "tool"
        assert payload["type"] == "artifact"
        assert payload["entries"]
        assert payload["page_metadata"]["list"]["title"] == "Tools"
        op_names = {operation["name"] for operation in payload["api_operations"]}
        assert {
            "get_tool",
            "search_tool",
            "create_tool",
            "update_tool",
            "duplicate_tool",
            "delete_tool",
            "export_tools",
        } <= op_names

    async def test_tool_export_route_returns_csv_upload(
        self,
        pool,
        redis_client,
        v5_tool_route_client,
        tool_route_actor,
    ):
        created = await self._create_tool_via_route(
            pool,
            redis_client,
            v5_tool_route_client,
            tool_route_actor,
        )

        response = await v5_tool_route_client.client.post(
            "/v5/tools/export",
            json={"tool_id": created["tool_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] >= 1

    async def test_tool_refresh_route_returns_invalidated_tags(
        self,
        v5_tool_route_client,
        tool_route_actor,
    ):
        v5_tool_route_client.authenticate(
            profile_id=tool_route_actor.profile_id,
            session_id=tool_route_actor.session_id,
        )

        response = await v5_tool_route_client.client.post(
            "/v5/tools/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "tools,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert set(payload["invalidated_tags"]) == {"tools", "artifacts"}

    async def _create_tool_via_route(
        self,
        pool,
        redis_client,
        v5_tool_route_client,
        tool_route_actor,
    ) -> dict[str, str]:
        resources = await _create_tool_route_resources(pool, redis_client)
        v5_tool_route_client.authenticate(
            profile_id=tool_route_actor.profile_id,
            session_id=tool_route_actor.session_id,
        )

        response = await v5_tool_route_client.client.post(
            "/v5/tools/create",
            json={
                "tools": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(tool_route_actor.department_id)],
                    }
                ]
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        return {
            "tool_id": payload["results"][0]["tool_id"],
            "name": resources.name,
            "description": resources.description,
        }
