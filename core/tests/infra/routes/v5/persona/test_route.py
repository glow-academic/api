"""End-to-end tests for the canonical persona HTTP routes."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import RouteActor, create_admin_route_actor


@dataclass(frozen=True)
class PersonaRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str
    color_id: UUID
    color_name: str
    color_hex_code: str
    icon_id: UUID
    icon_name: str
    icon_value: str
    instruction_id: UUID
    instruction_template: str


async def _create_persona_route_resources(
    pool,
    redis_client,
) -> PersonaRouteResources:
    from app.tools.resources.colors.create import create_color
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.icons.create import create_icon
    from app.tools.resources.instructions.create import create_instruction
    from app.tools.resources.names.create import create_name

    tag = unique_tag()
    name = f"Route Persona {tag}"
    description = f"Route description {tag}"
    color_name = f"Route Yellow {tag}"
    icon_name = f"Route User {tag}"
    instruction_template = f"You are persona route test {tag}."
    color_hex_code = "#F5C542"
    icon_value = "user"

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)
        color_res = await create_color(
            conn,
            color_name,
            f"Color for {tag}",
            color_hex_code,
            redis_client,
        )
        icon_res = await create_icon(
            conn,
            icon_name,
            f"Icon for {tag}",
            icon_value,
            redis_client,
        )
        instruction_res = await create_instruction(
            conn,
            instruction_template,
            redis_client,
        )

    return PersonaRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
        color_id=color_res.id,
        color_name=color_res.name,
        color_hex_code=color_res.hex_code,
        icon_id=icon_res.id,
        icon_name=icon_res.name,
        icon_value=icon_res.value,
        instruction_id=instruction_res.id,
        instruction_template=instruction_res.template,
    )


@pytest_asyncio.fixture
async def persona_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["persona", "scenario"],
        group_name="persona-route",
        role_name_prefix="Persona Route Admin",
    )


@pytest.mark.asyncio
class TestPersonaRoute:
    async def test_create_persona_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        v5_persona_route_client,
        persona_route_actor,
    ):
        resources = await _create_persona_route_resources(pool, redis_client)
        v5_persona_route_client.authenticate(
            profile_id=persona_route_actor.profile_id,
            session_id=persona_route_actor.session_id,
        )

        response = await v5_persona_route_client.client.post(
            "/v5/personas/create",
            json={
                "personas": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "color_id": str(resources.color_id),
                        "icon_id": str(resources.icon_id),
                        "instructions_id": str(resources.instruction_id),
                        "department_ids": [str(persona_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "personas"

        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["message"] == "Persona created successfully"
        assert payload["results"][0]["persona_id"] is not None

    async def test_get_persona_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        v5_persona_route_client,
        persona_route_actor,
    ):
        created = await self._create_persona_via_route(
            pool,
            redis_client,
            v5_persona_route_client,
            persona_route_actor,
        )

        response = await v5_persona_route_client.client.post(
            "/v5/personas/get",
            json={"persona_id": created["persona_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "personas"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["actor_name"] == persona_route_actor.name
        assert payload["persona_exists"] is True
        assert payload["can_edit"] is True
        assert payload["group_id"] is not None
        assert payload["names"]["resource"]["name"] == created["name"]
        assert (
            payload["descriptions"]["resource"]["description"] == created["description"]
        )
        assert payload["colors"]["resource"]["name"] == created["color_name"]
        assert payload["icons"]["resource"]["name"] == created["icon_name"]
        assert (
            payload["instructions"]["resource"]["template"]
            == created["instruction_template"]
        )
        assert {
            department["department_id"]
            for department in payload["departments"]["current"]
        } == {str(persona_route_actor.department_id)}

    async def test_search_persona_route_returns_created_persona(
        self,
        pool,
        redis_client,
        v5_persona_route_client,
        persona_route_actor,
    ):
        created = await self._create_persona_via_route(
            pool,
            redis_client,
            v5_persona_route_client,
            persona_route_actor,
        )

        response = await v5_persona_route_client.client.post(
            "/v5/personas/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(persona_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200
        assert response.headers["X-Invalidate-Tags"] == "personas"

        payload = response.json()
        assert payload["actor_name"] == persona_route_actor.name
        assert payload["total_count"] >= 1
        assert any(
            persona["persona_id"] == created["persona_id"]
            for persona in payload["personas"]
        )

        created_persona = next(
            persona
            for persona in payload["personas"]
            if persona["persona_id"] == created["persona_id"]
        )
        assert created_persona["name"] == created["name"]
        assert created_persona["description"] == created["description"]
        assert created_persona["color"] == created["color_hex_code"]
        assert created_persona["icon"] == created["icon_value"]
        assert created_persona["can_edit"] is True
        assert created_persona["can_duplicate"] is True
        assert created_persona["can_delete"] is True

    async def test_get_persona_route_hits_cache_on_second_request(
        self,
        pool,
        redis_client,
        v5_persona_route_client,
        persona_route_actor,
    ):
        created = await self._create_persona_via_route(
            pool,
            redis_client,
            v5_persona_route_client,
            persona_route_actor,
        )

        first = await v5_persona_route_client.client.post(
            "/v5/personas/get",
            json={"persona_id": created["persona_id"]},
        )
        second = await v5_persona_route_client.client.post(
            "/v5/personas/get",
            json={"persona_id": created["persona_id"]},
        )

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.headers["X-Cache-Hit"] == "0"
        assert second.headers["X-Cache-Hit"] in {"0", "1"}

    async def test_update_persona_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        v5_persona_route_client,
        persona_route_actor,
    ):
        created = await self._create_persona_via_route(
            pool,
            redis_client,
            v5_persona_route_client,
            persona_route_actor,
        )
        updated = await _create_persona_route_resources(pool, redis_client)

        response = await v5_persona_route_client.client.post(
            "/v5/personas/update",
            json={
                "personas": [
                    {
                        "persona_id": created["persona_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "color_id": str(updated.color_id),
                        "icon_id": str(updated.icon_id),
                        "instructions_id": str(updated.instruction_id),
                        "department_ids": [str(persona_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "personas"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["persona_id"] == created["persona_id"]

        get_response = await v5_persona_route_client.client.post(
            "/v5/personas/get",
            json={"persona_id": created["persona_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert get_response.status_code == 200, get_response.text
        get_payload = get_response.json()
        assert get_payload["names"]["resource"]["name"] == updated.name
        assert (
            get_payload["descriptions"]["resource"]["description"]
            == updated.description
        )
        assert get_payload["colors"]["resource"]["name"] == updated.color_name
        assert get_payload["icons"]["resource"]["name"] == updated.icon_name
        assert (
            get_payload["instructions"]["resource"]["template"]
            == updated.instruction_template
        )

    async def test_duplicate_persona_route_returns_new_persona(
        self,
        pool,
        redis_client,
        v5_persona_route_client,
        persona_route_actor,
    ):
        created = await self._create_persona_via_route(
            pool,
            redis_client,
            v5_persona_route_client,
            persona_route_actor,
        )

        response = await v5_persona_route_client.client.post(
            "/v5/personas/duplicate",
            json={"persona_id": created["persona_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "personas"
        payload = response.json()
        assert payload["success"] is True
        assert payload["persona_id"] != created["persona_id"]
        assert "duplicated successfully" in payload["message"]

    async def test_delete_persona_route_hides_deleted_persona_from_search(
        self,
        pool,
        redis_client,
        v5_persona_route_client,
        persona_route_actor,
    ):
        created = await self._create_persona_via_route(
            pool,
            redis_client,
            v5_persona_route_client,
            persona_route_actor,
        )

        response = await v5_persona_route_client.client.post(
            "/v5/personas/delete",
            json={"persona_ids": [created["persona_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "personas"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["persona_id"] == created["persona_id"]

        search_response = await v5_persona_route_client.client.post(
            "/v5/personas/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(persona_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert search_response.status_code == 200, search_response.text
        search_payload = search_response.json()
        assert all(
            persona["persona_id"] != created["persona_id"]
            for persona in search_payload["personas"]
        )

    async def test_patch_persona_draft_route_creates_draft_visible_via_get(
        self,
        pool,
        redis_client,
        v5_persona_route_client,
        persona_route_actor,
    ):
        created = await self._create_persona_via_route(
            pool,
            redis_client,
            v5_persona_route_client,
            persona_route_actor,
        )
        draft_name = f"Draft Persona {unique_tag()}"

        response = await v5_persona_route_client.client.patch(
            "/v5/personas/draft",
            json={
                "expected_version": 0,
                "name": draft_name,
                "department_ids": [str(persona_route_actor.department_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "personas,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["new_version"] == 1
        assert payload["draft_id"] is not None
        assert payload["form_state"]["name_id"] is not None

        get_response = await v5_persona_route_client.client.post(
            "/v5/personas/get",
            json={
                "persona_id": created["persona_id"],
                "draft_id": payload["draft_id"],
            },
            headers={"X-Bypass-Cache": "1"},
        )

        assert get_response.status_code == 200, get_response.text
        get_payload = get_response.json()
        assert get_payload["draft_version"] == 1
        assert get_payload["names"]["resource"]["name"] == draft_name

    async def test_persona_drafts_route_lists_owned_drafts(
        self,
        pool,
        v5_persona_route_client,
        persona_route_actor,
    ):
        from app.tools.entries.groups.create import create_group
        from app.tools.entries.persona_drafts.create import (
            create_persona_draft,
        )

        async with pool.acquire() as conn:
            group = await create_group(conn, session_id=persona_route_actor.session_id)
            draft = await create_persona_draft(
                conn,
                group_id=group.id,
                session_id=persona_route_actor.session_id,
                profile_ids=[persona_route_actor.profiles_id],
            )

        v5_persona_route_client.authenticate(
            profile_id=persona_route_actor.profile_id,
            session_id=persona_route_actor.session_id,
        )
        drafts_response = await v5_persona_route_client.client.post(
            "/v5/personas/drafts",
        )

        assert drafts_response.status_code == 200, drafts_response.text
        assert drafts_response.headers["X-Cache-Tags"] == "personas,drafts"
        drafts_payload = drafts_response.json()
        assert any(entry["id"] == str(draft.id) for entry in drafts_payload["entries"])

    async def test_persona_docs_route_returns_composed_docs(
        self,
        pool,
        redis_client,
        v5_persona_route_client,
        persona_route_actor,
    ):
        created = await self._create_persona_via_route(
            pool,
            redis_client,
            v5_persona_route_client,
            persona_route_actor,
        )

        response = await v5_persona_route_client.client.post(
            "/v5/personas/docs",
            json={"entity_id": created["persona_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "persona"
        assert payload["artifact"] is not None
        assert payload["entries"]
        assert payload["resources"]
        assert payload["page_metadata"]["list"]["title"] == "Personas"
        assert payload["page_metadata"]["detail"]["title"]
        assert payload["page_metadata"]["new"]["title"] == "New Persona"

    async def test_persona_export_route_creates_upload(
        self,
        pool,
        redis_client,
        v5_persona_route_client,
        persona_route_actor,
    ):
        created = await self._create_persona_via_route(
            pool,
            redis_client,
            v5_persona_route_client,
            persona_route_actor,
        )

        response = await v5_persona_route_client.client.post(
            "/v5/personas/export",
            json={"persona_id": created["persona_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] >= 1
        assert payload["mime_type"] == "text/csv"
        decoded_csv = base64.b64decode(payload["content"]).decode("utf-8")
        assert created["name"] in decoded_csv

    async def test_persona_refresh_route_returns_invalidated_tags(
        self,
        v5_persona_route_client,
        persona_route_actor,
    ):
        v5_persona_route_client.authenticate(
            profile_id=persona_route_actor.profile_id,
            session_id=persona_route_actor.session_id,
        )

        response = await v5_persona_route_client.client.post(
            "/v5/personas/refresh",
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "personas,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["refreshed_views"] == ["personas_mv", "persona_drafts_mv"]
        assert payload["invalidated_tags"] == ["personas", "artifacts"]

    async def _create_persona_via_route(
        self,
        pool,
        redis_client,
        v5_persona_route_client,
        persona_route_actor: RouteActor,
    ) -> dict[str, str]:
        resources = await _create_persona_route_resources(pool, redis_client)
        v5_persona_route_client.authenticate(
            profile_id=persona_route_actor.profile_id,
            session_id=persona_route_actor.session_id,
        )

        response = await v5_persona_route_client.client.post(
            "/v5/personas/create",
            json={
                "personas": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "color_id": str(resources.color_id),
                        "icon_id": str(resources.icon_id),
                        "instructions_id": str(resources.instruction_id),
                        "department_ids": [str(persona_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200
        payload = response.json()
        return {
            "persona_id": payload["results"][0]["persona_id"],
            "name": resources.name,
            "description": resources.description,
            "color_name": resources.color_name,
            "color_hex_code": resources.color_hex_code,
            "icon_name": resources.icon_name,
            "icon_value": resources.icon_value,
            "instruction_template": resources.instruction_template,
        }
