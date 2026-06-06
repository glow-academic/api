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


async def test_sync_is_atomic_on_midway_failure(
    pool, redis_client, sync_fixture, monkeypatch
):
    """A failure partway through the create sequence must leave NO partial rows.

    ``sync_home_practice_entries`` performs many dependent writes per simulation:
    the ``practice_entry`` parent row, its 7 junction-table inserts, then a
    ``chat_entry`` plus its junctions, then the ``practice_chat`` link — all on
    one acquired connection. These are wrapped in a single
    ``async with conn.transaction():`` so that if any later write fails, the
    already-written parent + junctions roll back instead of being committed
    (autocommit) as an orphaned, half-built practice entry.

    Regression: inject a failure on ``create_chat`` (which runs AFTER the
    practice parent + junctions are written) and assert the practice_entry
    parent was rolled back. Before the transaction wrap, the parent persisted.
    """

    async def _baseline_count(table: str) -> int:
        async with pool.acquire() as conn:
            return await conn.fetchval(f"SELECT count(*) FROM {table}")

    before_practice = await _baseline_count("practice_entry")
    before_conn = await _baseline_count("practice_simulations_connection")

    # create_chat is imported lazily inside sync_home_practice_entries via
    # `from app.tools.entries.chat.create import create_chat`, so patch the
    # source module attribute. It runs only after the practice parent row and
    # all 7 of its junction inserts have been issued on the same connection.
    import app.tools.entries.chat.create as chat_create_mod

    async def _boom(*args, **kwargs):
        raise RuntimeError("injected failure after practice parent was written")

    monkeypatch.setattr(chat_create_mod, "create_chat", _boom)

    with pytest.raises(RuntimeError, match="injected failure"):
        await sync_home_practice_entries(
            pool=pool,
            cohorts_resource_id=sync_fixture["cohort_id"],
            simulation_ids=[sync_fixture["simulation_id"]],
            simulation_position_ids=[],
            simulation_availability_ids=[],
            department_ids=[],
            profile_ids=[sync_fixture["profile_id"]],
            profile_persona_ids=[],
        )

    after_practice = await _baseline_count("practice_entry")
    after_conn = await _baseline_count("practice_simulations_connection")

    # Atomicity: the parent practice_entry and its junction rows written before
    # the failure must have been rolled back — no orphaned/partial state.
    assert after_practice == before_practice, (
        "practice_entry parent row leaked after a mid-sequence failure "
        "(writes were not wrapped in a transaction)"
    )
    assert after_conn == before_conn, (
        "practice_simulations_connection junction row leaked after a "
        "mid-sequence failure (writes were not wrapped in a transaction)"
    )
