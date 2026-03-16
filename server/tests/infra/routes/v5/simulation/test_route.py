"""End-to-end tests for the canonical simulation HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import create_admin_route_actor


@dataclass(frozen=True)
class SimulationRouteResources:
    name_id: UUID
    name: str
    description_id: UUID
    description: str
    scenario_id: UUID
    scenario_name: str


async def _create_simulation_route_resources(
    pool, redis_client
) -> SimulationRouteResources:
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.names.create import create_name
    from app.tools.resources.scenarios.create import create_scenario

    tag = unique_tag()
    name = f"Route Simulation {tag}"
    description = f"Route simulation description {tag}"
    scenario_name = f"Route Scenario {tag}"

    async with pool.acquire() as conn:
        name_res = await create_name(conn, name, redis_client)
        description_res = await create_description(conn, description, redis_client)
        scenario_res = await create_scenario(
            conn,
            name=scenario_name,
            description=f"Scenario for {tag}",
            redis=redis_client,
        )

    return SimulationRouteResources(
        name_id=name_res.id,
        name=name_res.name,
        description_id=description_res.id,
        description=description_res.description,
        scenario_id=scenario_res.id,
        scenario_name=scenario_res.name or scenario_name,
    )


@pytest_asyncio.fixture
async def simulation_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["simulation", "scenario", "persona"],
        group_name="simulation-route",
        role_name_prefix="Simulation Route Admin",
    )


@pytest.mark.asyncio
class TestSimulationRoute:
    async def test_create_simulation_route_uses_real_http_stack(
        self,
        pool,
        redis_client,
        v5_simulation_route_client,
        simulation_route_actor,
    ):
        resources = await _create_simulation_route_resources(pool, redis_client)
        v5_simulation_route_client.authenticate(
            profile_id=simulation_route_actor.profile_id,
            session_id=simulation_route_actor.session_id,
        )

        response = await v5_simulation_route_client.client.post(
            "/v5/simulations/create",
            json={
                "simulations": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(simulation_route_actor.department_id)],
                        "scenario_ids": [str(resources.scenario_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "simulations"
        payload = response.json()
        assert payload["results"][0]["success"] is True
        assert payload["results"][0]["simulation_id"] is not None

    async def test_get_simulation_route_returns_canonical_bundle(
        self,
        pool,
        redis_client,
        v5_simulation_route_client,
        simulation_route_actor,
    ):
        created = await self._create_simulation_via_route(
            pool,
            redis_client,
            v5_simulation_route_client,
            simulation_route_actor,
        )

        response = await v5_simulation_route_client.client.post(
            "/v5/simulations/get",
            json={"simulation_id": created["simulation_id"]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "simulations"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["actor_name"] == simulation_route_actor.name
        assert payload["simulation_exists"] is True
        assert payload["group_id"] is not None
        assert payload["names"]["resource"]["name"] == created["name"]
        assert (
            payload["descriptions"]["resource"]["description"] == created["description"]
        )
        assert any(
            scenario["scenario_id"] == created["scenario_id"]
            for scenario in payload["scenarios"]["current"]
        )

    async def test_search_simulation_route_returns_created_simulation(
        self,
        pool,
        redis_client,
        v5_simulation_route_client,
        simulation_route_actor,
    ):
        created = await self._create_simulation_via_route(
            pool,
            redis_client,
            v5_simulation_route_client,
            simulation_route_actor,
        )

        response = await v5_simulation_route_client.client.post(
            "/v5/simulations/search",
            json={
                "search": created["name"],
                "filter_department_ids": [str(simulation_route_actor.department_id)],
                "page_size": 10,
                "page_offset": 0,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "simulations"
        payload = response.json()
        assert payload["actor_name"] == simulation_route_actor.name
        assert payload["total_count"] >= 1
        assert any(
            simulation["simulation_id"] == created["simulation_id"]
            for simulation in payload["simulations"]
        )

    async def test_update_simulation_route_updates_visible_fields(
        self,
        pool,
        redis_client,
        v5_simulation_route_client,
        simulation_route_actor,
    ):
        created = await self._create_simulation_via_route(
            pool,
            redis_client,
            v5_simulation_route_client,
            simulation_route_actor,
        )
        updated = await _create_simulation_route_resources(pool, redis_client)

        response = await v5_simulation_route_client.client.post(
            "/v5/simulations/update",
            json={
                "simulations": [
                    {
                        "simulation_id": created["simulation_id"],
                        "name_id": str(updated.name_id),
                        "description_id": str(updated.description_id),
                        "department_ids": [str(simulation_route_actor.department_id)],
                        "scenario_ids": [str(updated.scenario_id)],
                    }
                ]
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "simulations"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_delete_simulation_route_soft_deletes_simulation(
        self,
        pool,
        redis_client,
        v5_simulation_route_client,
        simulation_route_actor,
    ):
        created = await self._create_simulation_via_route(
            pool,
            redis_client,
            v5_simulation_route_client,
            simulation_route_actor,
        )

        response = await v5_simulation_route_client.client.post(
            "/v5/simulations/delete",
            json={"simulation_ids": [created["simulation_id"]]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "simulations"
        payload = response.json()
        assert payload["results"][0]["success"] is True

    async def test_duplicate_simulation_route_creates_new_simulation(
        self,
        pool,
        redis_client,
        v5_simulation_route_client,
        simulation_route_actor,
    ):
        created = await self._create_simulation_via_route(
            pool,
            redis_client,
            v5_simulation_route_client,
            simulation_route_actor,
        )

        response = await v5_simulation_route_client.client.post(
            "/v5/simulations/duplicate",
            json={"simulation_id": created["simulation_id"]},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "simulations"
        payload = response.json()
        assert payload["success"] is True
        assert payload["simulation_id"] != created["simulation_id"]

    async def test_simulation_draft_route_creates_server_authoritative_draft(
        self,
        pool,
        redis_client,
        v5_simulation_route_client,
        simulation_route_actor,
    ):
        resources = await _create_simulation_route_resources(pool, redis_client)
        v5_simulation_route_client.authenticate(
            profile_id=simulation_route_actor.profile_id,
            session_id=simulation_route_actor.session_id,
        )

        response = await v5_simulation_route_client.client.patch(
            "/v5/simulations/draft",
            json={
                "expected_version": 0,
                "name_id": str(resources.name_id),
                "description_id": str(resources.description_id),
                "department_ids": [str(simulation_route_actor.department_id)],
                "scenario_ids": [str(resources.scenario_id)],
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "simulations,drafts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["new_version"] == 1

    async def test_simulation_drafts_route_lists_owned_drafts(
        self,
        pool,
        redis_client,
        v5_simulation_route_client,
        simulation_route_actor,
    ):
        resources = await _create_simulation_route_resources(pool, redis_client)
        v5_simulation_route_client.authenticate(
            profile_id=simulation_route_actor.profile_id,
            session_id=simulation_route_actor.session_id,
        )
        draft_response = await v5_simulation_route_client.client.patch(
            "/v5/simulations/draft",
            json={"expected_version": 0, "name_id": str(resources.name_id)},
        )
        assert draft_response.status_code == 200, draft_response.text

        response = await v5_simulation_route_client.client.post(
            "/v5/simulations/drafts",
            json={},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "simulations,drafts"
        payload = response.json()
        assert payload["entries"]

    async def test_simulation_docs_route_returns_composed_docs(
        self,
        v5_simulation_route_client,
        simulation_route_actor,
    ):
        v5_simulation_route_client.authenticate(
            profile_id=simulation_route_actor.profile_id,
            session_id=simulation_route_actor.session_id,
        )

        response = await v5_simulation_route_client.client.post(
            "/v5/simulations/docs",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "simulation"
        assert payload["type"] == "artifact"
        assert payload["entries"]
        assert payload["page_metadata"]["list"]["title"] == "Simulations"

    async def test_simulation_export_route_returns_csv_upload(
        self,
        pool,
        redis_client,
        v5_simulation_route_client,
        simulation_route_actor,
    ):
        created = await self._create_simulation_via_route(
            pool,
            redis_client,
            v5_simulation_route_client,
            simulation_route_actor,
        )

        response = await v5_simulation_route_client.client.post(
            "/v5/simulations/export",
            json={"simulation_id": created["simulation_id"]},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".csv")
        assert payload["row_count"] >= 1

    async def test_simulation_refresh_route_returns_invalidated_tags(
        self,
        v5_simulation_route_client,
        simulation_route_actor,
    ):
        v5_simulation_route_client.authenticate(
            profile_id=simulation_route_actor.profile_id,
            session_id=simulation_route_actor.session_id,
        )

        response = await v5_simulation_route_client.client.post(
            "/v5/simulations/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "simulations,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert set(payload["invalidated_tags"]) == {"simulations", "artifacts"}

    async def _create_simulation_via_route(
        self,
        pool,
        redis_client,
        v5_simulation_route_client,
        simulation_route_actor,
    ) -> dict[str, str]:
        resources = await _create_simulation_route_resources(pool, redis_client)
        v5_simulation_route_client.authenticate(
            profile_id=simulation_route_actor.profile_id,
            session_id=simulation_route_actor.session_id,
        )

        response = await v5_simulation_route_client.client.post(
            "/v5/simulations/create",
            json={
                "simulations": [
                    {
                        "name_id": str(resources.name_id),
                        "description_id": str(resources.description_id),
                        "department_ids": [str(simulation_route_actor.department_id)],
                        "scenario_ids": [str(resources.scenario_id)],
                    }
                ]
            },
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        return {
            "simulation_id": payload["results"][0]["simulation_id"],
            "name": resources.name,
            "description": resources.description,
            "scenario_id": str(resources.scenario_id),
        }
