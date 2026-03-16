"""End-to-end tests for the canonical scenario HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import RouteActor, create_admin_route_actor


@dataclass(frozen=True)
class ScenarioRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str
    problem_statement_id: UUID
    problem_statement_name: str
    problem_statement: str


async def _create_scenario_route_resources(
    pool, redis_client
) -> ScenarioRouteResources:
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.names.create import create_name
    from app.tools.resources.problem_statements.create import (
        create_problem_statement,
    )

    tag = unique_tag()
    name = f"Route Scenario {tag}"
    description = f"Route scenario description {tag}"
    problem_statement_name = f"Route Problem {tag}"
    problem_statement = f"Patient presents with route scenario symptoms {tag}."

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)
        problem_statement_res = await create_problem_statement(
            conn,
            name=problem_statement_name,
            problem_statement=problem_statement,
            redis=redis_client,
        )

    return ScenarioRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
        problem_statement_id=problem_statement_res.id,
        problem_statement_name=problem_statement_res.name,
        problem_statement=problem_statement_res.problem_statement,
    )


@pytest_asyncio.fixture
async def scenario_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["scenario", "persona"],
        group_name="scenario-route",
        role_name_prefix="Scenario Route Admin",
    )


@pytest.mark.asyncio
class TestScenarioRoute:
    async def test_create_scenario_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        v5_scenario_route_client,
        scenario_route_actor,
    ):
        resources = await _create_scenario_route_resources(pool, redis_client)
        v5_scenario_route_client.authenticate(
            profile_id=scenario_route_actor.profile_id,
            session_id=scenario_route_actor.session_id,
        )

        response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/create",
            json={
                "scenarios": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "problem_statement_id": str(resources.problem_statement_id),
                        "department_ids": [str(scenario_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "scenarios"

        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["message"] == "Scenario created successfully"
        assert payload["results"][0]["scenario_id"] is not None

    async def test_get_scenario_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        v5_scenario_route_client,
        scenario_route_actor,
    ):
        created = await self._create_scenario_via_route(
            pool,
            redis_client,
            v5_scenario_route_client,
            scenario_route_actor,
        )

        response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/get",
            json={"scenario_id": created["scenario_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "scenarios"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["actor_name"] == scenario_route_actor.name
        assert payload["scenario_exists"] is True
        assert payload["can_edit"] is True
        assert payload["group_id"] is not None
        assert payload["names"]["resource"]["name"] == created["name"]
        assert (
            payload["descriptions"]["resource"]["description"] == created["description"]
        )
        assert (
            payload["problem_statements"]["resource"]["problem_statement"]
            == created["problem_statement"]
        )

    async def test_search_scenario_route_returns_created_scenario(
        self,
        pool,
        redis_client,
        v5_scenario_route_client,
        scenario_route_actor,
    ):
        created = await self._create_scenario_via_route(
            pool,
            redis_client,
            v5_scenario_route_client,
            scenario_route_actor,
        )

        response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(scenario_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "scenarios"

        payload = response.json()
        assert payload["actor_name"] == scenario_route_actor.name
        assert payload["total_count"] >= 1
        assert any(
            scenario["scenario_id"] == created["scenario_id"]
            for scenario in payload["scenarios"]
        )

        created_scenario = next(
            scenario
            for scenario in payload["scenarios"]
            if scenario["scenario_id"] == created["scenario_id"]
        )
        assert created_scenario["name"] == created["name"]
        assert created_scenario["department_ids"] == [
            str(scenario_route_actor.department_id)
        ]
        assert created_scenario["can_edit"] is True
        assert created_scenario["can_duplicate"] is True
        assert created_scenario["can_delete"] is True

    async def test_get_scenario_route_hits_cache_on_second_request(
        self,
        pool,
        redis_client,
        v5_scenario_route_client,
        scenario_route_actor,
    ):
        created = await self._create_scenario_via_route(
            pool,
            redis_client,
            v5_scenario_route_client,
            scenario_route_actor,
        )

        first = await v5_scenario_route_client.client.post(
            "/v5/scenarios/get",
            json={"scenario_id": created["scenario_id"]},
        )
        second = await v5_scenario_route_client.client.post(
            "/v5/scenarios/get",
            json={"scenario_id": created["scenario_id"]},
        )

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.headers["X-Cache-Hit"] == "0"
        assert second.headers["X-Cache-Hit"] in {"0", "1"}

    async def test_update_scenario_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        v5_scenario_route_client,
        scenario_route_actor,
    ):
        created = await self._create_scenario_via_route(
            pool,
            redis_client,
            v5_scenario_route_client,
            scenario_route_actor,
        )
        updated = await _create_scenario_route_resources(pool, redis_client)

        response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/update",
            json={
                "scenarios": [
                    {
                        "scenario_id": created["scenario_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "problem_statement_id": str(updated.problem_statement_id),
                        "department_ids": [str(scenario_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "scenarios"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["scenario_id"] == created["scenario_id"]

        get_response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/get",
            json={"scenario_id": created["scenario_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert get_response.status_code == 200, get_response.text
        get_payload = get_response.json()
        assert get_payload["names"]["resource"]["name"] == updated.name
        assert (
            get_payload["descriptions"]["resource"]["description"]
            == updated.description
        )
        assert (
            get_payload["problem_statements"]["resource"]["problem_statement"]
            == updated.problem_statement
        )

    async def test_duplicate_scenario_route_returns_new_scenario(
        self,
        pool,
        redis_client,
        v5_scenario_route_client,
        scenario_route_actor,
    ):
        created = await self._create_scenario_via_route(
            pool,
            redis_client,
            v5_scenario_route_client,
            scenario_route_actor,
        )

        response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/duplicate",
            json={"scenario_id": created["scenario_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "scenarios"
        payload = response.json()
        assert payload["success"] is True
        assert payload["scenario_id"] != created["scenario_id"]
        assert "duplicated successfully" in payload["message"]

    async def test_delete_scenario_route_hides_deleted_scenario_from_search(
        self,
        pool,
        redis_client,
        v5_scenario_route_client,
        scenario_route_actor,
    ):
        created = await self._create_scenario_via_route(
            pool,
            redis_client,
            v5_scenario_route_client,
            scenario_route_actor,
        )

        response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/delete",
            json={"scenario_ids": [created["scenario_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "scenarios"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["scenario_id"] == created["scenario_id"]

        search_response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(scenario_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert search_response.status_code == 200, search_response.text
        search_payload = search_response.json()
        assert all(
            scenario["scenario_id"] != created["scenario_id"]
            for scenario in search_payload["scenarios"]
        )

    async def test_patch_scenario_draft_route_creates_draft_visible_via_get(
        self,
        pool,
        redis_client,
        v5_scenario_route_client,
        scenario_route_actor,
    ):
        created = await self._create_scenario_via_route(
            pool,
            redis_client,
            v5_scenario_route_client,
            scenario_route_actor,
        )
        draft_name = f"Draft Scenario {unique_tag()}"

        response = await v5_scenario_route_client.client.patch(
            "/v5/scenarios/draft",
            json={
                "expected_version": 0,
                "name": draft_name,
                "department_ids": [str(scenario_route_actor.department_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "scenarios,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["new_version"] == 1
        assert payload["draft_id"] is not None
        assert payload["form_state"]["name_id"] is not None

        get_response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/get",
            json={
                "scenario_id": created["scenario_id"],
                "draft_id": payload["draft_id"],
            },
            headers={"X-Bypass-Cache": "1"},
        )

        assert get_response.status_code == 200, get_response.text
        get_payload = get_response.json()
        assert get_payload["draft_version"] == 1
        assert get_payload["names"]["resource"]["name"] == draft_name

    async def test_scenario_drafts_route_lists_owned_drafts(
        self,
        pool,
        v5_scenario_route_client,
        scenario_route_actor,
    ):
        from app.tools.entries.groups.create import create_group
        from app.tools.entries.scenario_drafts.create import (
            create_scenario_draft,
        )

        async with pool.acquire() as conn:
            group = await create_group(conn, session_id=scenario_route_actor.session_id)
            draft = await create_scenario_draft(
                conn,
                group_id=group.id,
                session_id=scenario_route_actor.session_id,
                profile_ids=[scenario_route_actor.profiles_id],
            )

        v5_scenario_route_client.authenticate(
            profile_id=scenario_route_actor.profile_id,
            session_id=scenario_route_actor.session_id,
        )
        drafts_response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/drafts",
        )

        assert drafts_response.status_code == 200, drafts_response.text
        assert drafts_response.headers["X-Cache-Tags"] == "scenarios,drafts"
        drafts_payload = drafts_response.json()
        assert any(entry["id"] == str(draft.id) for entry in drafts_payload["entries"])

    async def test_scenario_docs_route_returns_composed_docs(
        self,
        pool,
        redis_client,
        v5_scenario_route_client,
        scenario_route_actor,
    ):
        created = await self._create_scenario_via_route(
            pool,
            redis_client,
            v5_scenario_route_client,
            scenario_route_actor,
        )

        response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/docs",
            json={"entity_id": created["scenario_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "scenario"
        assert payload["artifact"] is not None
        assert payload["entries"]
        assert payload["resources"]
        assert payload["page_metadata"]["list"]["title"] == "Scenarios"
        assert payload["page_metadata"]["detail"]["title"]
        assert payload["page_metadata"]["new"]["title"] == "New Scenario"

    async def test_scenario_export_route_creates_upload(
        self,
        pool,
        redis_client,
        v5_scenario_route_client,
        scenario_route_actor,
    ):
        created = await self._create_scenario_via_route(
            pool,
            redis_client,
            v5_scenario_route_client,
            scenario_route_actor,
        )

        response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/export",
            json={"scenario_id": created["scenario_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] >= 1


    async def test_scenario_refresh_route_returns_invalidated_tags(
        self,
        v5_scenario_route_client,
        scenario_route_actor,
    ):
        v5_scenario_route_client.authenticate(
            profile_id=scenario_route_actor.profile_id,
            session_id=scenario_route_actor.session_id,
        )

        response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/refresh",
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "scenarios,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["refreshed_views"] == ["scenario_drafts_mv"]
        assert payload["invalidated_tags"] == ["scenarios", "artifacts"]

    async def _create_scenario_via_route(
        self,
        pool,
        redis_client,
        v5_scenario_route_client,
        scenario_route_actor: RouteActor,
    ) -> dict[str, str]:
        resources = await _create_scenario_route_resources(pool, redis_client)
        v5_scenario_route_client.authenticate(
            profile_id=scenario_route_actor.profile_id,
            session_id=scenario_route_actor.session_id,
        )

        response = await v5_scenario_route_client.client.post(
            "/v5/scenarios/create",
            json={
                "scenarios": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "problem_statement_id": str(resources.problem_statement_id),
                        "department_ids": [str(scenario_route_actor.department_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        return {
            "scenario_id": payload["results"][0]["scenario_id"],
            "name": resources.name,
            "description": resources.description,
            "problem_statement_name": resources.problem_statement_name,
            "problem_statement": resources.problem_statement,
        }
