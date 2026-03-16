"""Integration tests for infra.home_practice_sync — real DB, no mocks.

Exercises sync_home_practice_entries with real simulation/scenario data
to verify correct attribute access on resource response types.
"""

import pytest
import pytest_asyncio

from app.infra.home_practice_sync import sync_home_practice_entries

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def sync_fixture(pool, redis_client):
    """Create the minimum resource graph needed for sync_home_practice_entries.

    Creates:
      - 1 scenario (scenarios_resource)
      - 1 simulation (simulations_resource) with scenario_ids + practice=True
      - 1 profile
      - 1 cohort (cohorts_resource)

    Returns a dict of IDs for use in tests.
    """
    from app.tools.resources.cohorts.create import create_cohort
    from app.tools.resources.profiles.create import create_profile
    from app.tools.resources.scenarios.create import create_scenario
    from app.tools.resources.simulations.create import create_simulation

    async with pool.acquire() as conn:
        profile = await create_profile(conn, redis_client)
        scenario = await create_scenario(conn, redis=redis_client)
        simulation = await create_simulation(conn, redis_client)
        cohort = await create_cohort(conn, redis_client)

        # Link scenario to simulation and set practice flag directly
        # (resource-level create doesn't set these denormalized fields)
        await conn.execute(
            """
            UPDATE simulations_resource
            SET scenario_ids = $1, practice = true
            WHERE id = $2
            """,
            [scenario.id],
            simulation.id,
        )

    return {
        "profile_id": profile.id,
        "scenario_id": scenario.id,
        "simulation_id": simulation.id,
        "cohort_id": cohort.id,
    }


async def test_sync_creates_practice_and_chat_entries(pool, redis_client, sync_fixture):
    """sync_home_practice_entries should create practice + chat entries.

    Regression test: GetSimulationResponse has 'id' not 'simulation_id',
    and GetScenarioResponse has 'id' not 'scenario_id'. Before the fix,
    this raises AttributeError.
    """
    count = await sync_home_practice_entries(
        pool=pool,
        cohorts_resource_id=sync_fixture["cohort_id"],
        simulation_ids=[sync_fixture["simulation_id"]],
        simulation_position_ids=[],
        simulation_availability_ids=[],
        department_ids=[],
        profile_ids=[sync_fixture["profile_id"]],
        profile_persona_ids=[],
    )

    # 1 practice entry + 1 chat entry = 2
    assert count == 2
