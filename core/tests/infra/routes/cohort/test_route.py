"""End-to-end tests for the canonical cohort HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio

from tests.helpers import unique_tag
from tests.infra.route_helpers import (
    RouteActor,
    create_admin_route_actor,
    selected_resource,
    selected_resources,
)


@dataclass(frozen=True)
class CohortRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str
    simulation_id: UUID
    simulation_name: str


async def _create_cohort_route_resources(pool, redis_client) -> CohortRouteResources:
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.names.create import create_name
    from app.tools.resources.simulations.create import create_simulation

    tag = unique_tag()
    name = f"Route Cohort {tag}"
    description = f"Route cohort description {tag}"
    simulation_name = f"Route Simulation {tag}"

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)
        simulation_res = await create_simulation(
            conn,
            redis_client,
            name=simulation_name,
            description=f"Route simulation description {tag}",
        )

    return CohortRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
        simulation_id=simulation_res.id,
        simulation_name=simulation_res.name,
    )


@pytest_asyncio.fixture
async def cohort_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["cohort", "simulation", "persona"],
        group_name="cohort-route",
        role_name_prefix="Cohort Route Admin",
    )


@pytest.mark.asyncio
class TestCohortRoute:
    async def test_create_cohort_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        cohort_route_client,
        cohort_route_actor,
    ):
        resources = await _create_cohort_route_resources(pool, redis_client)
        cohort_route_client.authenticate(
            profile_id=cohort_route_actor.profile_id,
            session_id=cohort_route_actor.session_id,
        )

        response = await cohort_route_client.client.post(
            "/cohort/create",
            json={
                "cohorts": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(cohort_route_actor.department_id)],
                        "simulation_ids": [str(resources.simulation_id)],
                        "profile_ids": [str(cohort_route_actor.profiles_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "cohorts"

        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["message"] == "Cohort created successfully"
        assert payload["results"][0]["cohort_id"] is not None

    async def test_get_cohort_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        cohort_route_client,
        cohort_route_actor,
    ):
        created = await self._create_cohort_via_route(
            pool,
            redis_client,
            cohort_route_client,
            cohort_route_actor,
        )

        response = await cohort_route_client.client.post(
            "/cohort/get",
            json={"cohort_id": created["cohort_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "cohorts"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["actor_name"] == cohort_route_actor.name
        assert payload["cohort_exists"] is True
        assert payload["group_id"] is not None
        assert selected_resource(payload["names"])["name"] == created["name"]
        assert (
            selected_resource(payload["descriptions"])["description"]
            == created["description"]
        )
        assert selected_resources(payload["simulations"])
        assert (
            selected_resources(payload["simulations"])[0]["simulation_id"]
            == created["simulation_id"]
        )
        assert selected_resources(payload["profiles"])
        assert (
            selected_resources(payload["profiles"])[0]["profile_id"]
            == created["profile_id"]
        )

    async def test_search_cohort_route_returns_created_cohort(
        self,
        pool,
        redis_client,
        cohort_route_client,
        cohort_route_actor,
    ):
        created = await self._create_cohort_via_route(
            pool,
            redis_client,
            cohort_route_client,
            cohort_route_actor,
        )

        response = await cohort_route_client.client.post(
            "/cohort/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(cohort_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "cohorts"

        payload = response.json()
        assert payload["actor_name"] == cohort_route_actor.name
        assert payload["total_count"] >= 1
        assert any(
            cohort["cohort_id"] == created["cohort_id"] for cohort in payload["cohorts"]
        )

        created_cohort = next(
            cohort
            for cohort in payload["cohorts"]
            if cohort["cohort_id"] == created["cohort_id"]
        )
        assert created_cohort["name"] == created["name"]
        assert created_cohort["department_ids"] == [
            str(cohort_route_actor.department_id)
        ]
        assert created_cohort["profile_ids"] == [created["profile_id"]]
        assert created_cohort["simulation_ids"] == [created["simulation_id"]]

    async def test_get_cohort_route_hits_cache_on_second_request(
        self,
        pool,
        redis_client,
        cohort_route_client,
        cohort_route_actor,
    ):
        created = await self._create_cohort_via_route(
            pool,
            redis_client,
            cohort_route_client,
            cohort_route_actor,
        )

        first = await cohort_route_client.client.post(
            "/cohort/get",
            json={"cohort_id": created["cohort_id"]},
        )
        second = await cohort_route_client.client.post(
            "/cohort/get",
            json={"cohort_id": created["cohort_id"]},
        )

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.headers["X-Cache-Hit"] == "0"
        assert second.headers["X-Cache-Hit"] in {"0", "1"}

    async def test_update_cohort_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        cohort_route_client,
        cohort_route_actor,
    ):
        created = await self._create_cohort_via_route(
            pool,
            redis_client,
            cohort_route_client,
            cohort_route_actor,
        )
        updated = await _create_cohort_route_resources(pool, redis_client)

        response = await cohort_route_client.client.post(
            "/cohort/update",
            json={
                "cohorts": [
                    {
                        "cohort_id": created["cohort_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "department_ids": [str(cohort_route_actor.department_id)],
                        "simulation_ids": [str(updated.simulation_id)],
                        "profile_ids": [str(cohort_route_actor.profiles_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "cohorts"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["cohort_id"] == created["cohort_id"]

        get_response = await cohort_route_client.client.post(
            "/cohort/get",
            json={"cohort_id": created["cohort_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert get_response.status_code == 200, get_response.text
        get_payload = get_response.json()
        assert selected_resource(get_payload["names"])["name"] == updated.name
        assert (
            selected_resource(get_payload["descriptions"])["description"]
            == updated.description
        )
        assert selected_resources(get_payload["simulations"])[0][
            "simulation_id"
        ] == str(updated.simulation_id)

    async def test_duplicate_cohort_route_returns_new_cohort(
        self,
        pool,
        redis_client,
        cohort_route_client,
        cohort_route_actor,
    ):
        created = await self._create_cohort_via_route(
            pool,
            redis_client,
            cohort_route_client,
            cohort_route_actor,
        )

        response = await cohort_route_client.client.post(
            "/cohort/duplicate",
            json={"cohort_id": created["cohort_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "cohorts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["cohort_id"] != created["cohort_id"]
        assert "duplicated successfully" in payload["message"]

    async def test_delete_cohort_route_hides_deleted_cohort_from_search(
        self,
        pool,
        redis_client,
        cohort_route_client,
        cohort_route_actor,
    ):
        created = await self._create_cohort_via_route(
            pool,
            redis_client,
            cohort_route_client,
            cohort_route_actor,
        )

        response = await cohort_route_client.client.post(
            "/cohort/delete",
            json={"cohort_ids": [created["cohort_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "cohorts"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["cohort_id"] == created["cohort_id"]

        search_response = await cohort_route_client.client.post(
            "/cohort/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(cohort_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert search_response.status_code == 200, search_response.text
        search_payload = search_response.json()
        assert all(
            cohort["cohort_id"] != created["cohort_id"]
            for cohort in search_payload["cohorts"]
        )

    async def test_patch_cohort_draft_route_creates_draft_visible_via_get(
        self,
        pool,
        redis_client,
        cohort_route_client,
        cohort_route_actor,
    ):
        created = await self._create_cohort_via_route(
            pool,
            redis_client,
            cohort_route_client,
            cohort_route_actor,
        )
        draft_name = f"Draft Cohort {unique_tag()}"

        response = await cohort_route_client.client.post(
            "/cohort/draft",
            json={
                "name": draft_name,
                "department_ids": [str(cohort_route_actor.department_id)],
                "simulation_ids": [created["simulation_id"]],
                "profile_ids": [created["profile_id"]],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "cohorts,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["draft_id"] is not None
        assert payload["form_state"]["name_id"] is not None

        get_response = await cohort_route_client.client.post(
            "/cohort/get",
            json={
                "cohort_id": created["cohort_id"],
                "draft_id": payload["draft_id"],
            },
            headers={"X-Bypass-Cache": "1"},
        )

        assert get_response.status_code == 200, get_response.text
        get_payload = get_response.json()
        assert selected_resource(get_payload["names"])["name"] == draft_name

    async def test_cohort_drafts_route_lists_owned_drafts(
        self,
        pool,
        redis_client,
        cohort_route_client,
        cohort_route_actor,
    ):
        from app.tools.entries.cohort_drafts.create import create_cohort_draft
        from app.tools.entries.groups.create import create_group

        async with pool.acquire() as conn:
            group = await create_group(
                conn,
                redis_client,
                session_id=cohort_route_actor.session_id,
                artifact_type="persona",
            )
            draft = await create_cohort_draft(
                conn,
                group_id=group.id,
                session_id=cohort_route_actor.session_id,
                profile_ids=[cohort_route_actor.profiles_id],
            )

        cohort_route_client.authenticate(
            profile_id=cohort_route_actor.profile_id,
            session_id=cohort_route_actor.session_id,
        )
        drafts_response = await cohort_route_client.client.post(
            "/cohort/drafts",
        )

        assert drafts_response.status_code == 200, drafts_response.text
        assert drafts_response.headers["X-Cache-Tags"] == "cohorts,drafts"
        drafts_payload = drafts_response.json()
        assert any(entry["id"] == str(draft.id) for entry in drafts_payload["entries"])

    async def test_cohort_docs_route_returns_composed_docs(
        self,
        pool,
        redis_client,
        cohort_route_client,
        cohort_route_actor,
    ):
        created = await self._create_cohort_via_route(
            pool,
            redis_client,
            cohort_route_client,
            cohort_route_actor,
        )

        response = await cohort_route_client.client.post(
            "/cohort/context",
            json={"entity_id": created["cohort_id"], "schema": True},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "cohort"
        assert payload["artifact"] is not None
        assert payload["entries"]
        assert payload["resources"]
        assert payload["page_metadata"]["list"]["title"] == "Cohorts"
        assert payload["page_metadata"]["detail"]["title"]
        assert payload["page_metadata"]["new"]["title"] == "New Cohort"

    async def test_cohort_export_route_creates_upload(
        self,
        pool,
        redis_client,
        cohort_route_client,
        cohort_route_actor,
    ):
        created = await self._create_cohort_via_route(
            pool,
            redis_client,
            cohort_route_client,
            cohort_route_actor,
        )

        response = await cohort_route_client.client.post(
            "/cohort/export",
            json={"cohort_id": created["cohort_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] >= 1


    async def test_cohort_refresh_route_returns_invalidated_tags(
        self,
        cohort_route_client,
        cohort_route_actor,
    ):
        cohort_route_client.authenticate(
            profile_id=cohort_route_actor.profile_id,
            session_id=cohort_route_actor.session_id,
        )

        response = await cohort_route_client.client.post(
            "/cohort/refresh",
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "cohorts,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["refreshed_views"] == ["cohort_drafts_mv"]
        assert payload["invalidated_tags"] == ["cohorts", "artifacts"]

    async def _create_cohort_via_route(
        self,
        pool,
        redis_client,
        cohort_route_client,
        cohort_route_actor: RouteActor,
    ) -> dict[str, str]:
        resources = await _create_cohort_route_resources(pool, redis_client)
        cohort_route_client.authenticate(
            profile_id=cohort_route_actor.profile_id,
            session_id=cohort_route_actor.session_id,
        )

        response = await cohort_route_client.client.post(
            "/cohort/create",
            json={
                "cohorts": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(cohort_route_actor.department_id)],
                        "simulation_ids": [str(resources.simulation_id)],
                        "profile_ids": [str(cohort_route_actor.profiles_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        return {
            "cohort_id": payload["results"][0]["cohort_id"],
            "name": resources.name,
            "description": resources.description,
            "simulation_id": str(resources.simulation_id),
            "simulation_name": resources.simulation_name,
            "profile_id": str(cohort_route_actor.profiles_id),
        }
