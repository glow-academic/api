"""Regression: simulation create resolves scenario-artifact IDs to resource IDs.

Clients (and the simulation draft / ``/scenario/search``) surface
``scenario_artifact`` IDs, but ``simulation_scenarios_junction.scenarios_id``
references ``scenarios_resource(id)`` (constraint
``simulation_scenarios_scenario_id_fkey``). Before the fix,
``resolve_simulation_values`` passed the artifact ID straight through, and the
artifact-junction write blew up with a ``ForeignKeyViolationError`` → HTTP 500
on ``POST /simulation/create`` whenever ``scenario_ids`` was supplied.

These mutation-verified tests exercise the real DB pool through black-box
tools only (no raw SQL): they create a real ``scenarios_resource`` snapshot, a
real ``scenario_artifact`` linked to it, then prove (1) resolution rewrites the
artifact ID to its resource ID and (2) the artifact junction write that used to
500 now succeeds.
"""

from uuid import uuid4

import pytest

from app.infra.simulation.permissions_context import resolve_simulation_values
from app.infra.simulation.types import CreateSimulationItem
from app.tools.artifacts.scenario.create import create_scenario as create_scenario_artifact
from app.tools.artifacts.simulation.create import create_simulation as create_simulation_artifact
from app.tools.resources.scenarios.create import create_scenario as create_scenario_resource

pytestmark = pytest.mark.asyncio


async def _seed_scenario_artifact_with_resource(pool, redis_client) -> tuple:
    """Create a scenarios_resource snapshot + a scenario_artifact linked to it.

    Mirrors how seeded scenarios are shaped: the artifact owns a
    ``scenarios_resource`` row through ``scenario_scenarios_junction``. Returns
    ``(artifact_id, resource_id)``.
    """
    async with pool.acquire() as conn:
        resource = await create_scenario_resource(
            conn,
            redis_client,
            name=f"sim-fk-scenario-{uuid4().hex[:8]}",
        )
        artifact = await create_scenario_artifact(
            conn,
            scenario_ids=[resource.id],  # links artifact -> resource snapshot
        )
    return artifact.id, resource.id


async def test_resolve_rewrites_scenario_artifact_id_to_resource_id(
    pool, redis_client
):
    artifact_id, resource_id = await _seed_scenario_artifact_with_resource(
        pool, redis_client
    )

    item = CreateSimulationItem(name="sim-fk-name", scenario_ids=[artifact_id])
    errors = await resolve_simulation_values(
        pool, redis_client, item, is_create=True
    )

    assert errors == []
    # The client-supplied artifact ID must be rewritten to the resource ID the
    # junction FK references — not left as the artifact ID.
    assert item.scenario_ids == [resource_id]
    assert artifact_id not in item.scenario_ids


async def test_resolved_scenario_id_satisfies_junction_fk(pool, redis_client):
    """The resolved ID must INSERT into simulation_scenarios_junction (the FK
    that produced the live 500) without a ForeignKeyViolationError."""
    artifact_id, resource_id = await _seed_scenario_artifact_with_resource(
        pool, redis_client
    )

    item = CreateSimulationItem(name="sim-fk-name-2", scenario_ids=[artifact_id])
    await resolve_simulation_values(pool, redis_client, item, is_create=True)

    # This is the exact write path that raised
    # simulation_scenarios_scenario_id_fkey before the fix.
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_simulation_artifact(
                conn,
                name_id=item.name_id,
                scenario_ids=item.scenario_ids,
            )
    assert result.id is not None


async def test_unknown_scenario_id_passes_through_for_fk_to_validate(
    pool, redis_client
):
    """A non-artifact ID (e.g. an already-resolved resource ID re-submitted)
    is left untouched so the junction FK remains the source of truth."""
    not_an_artifact = uuid4()

    item = CreateSimulationItem(name="sim-fk-name-3", scenario_ids=[not_an_artifact])
    errors = await resolve_simulation_values(
        pool, redis_client, item, is_create=True
    )

    assert errors == []
    assert item.scenario_ids == [not_an_artifact]
