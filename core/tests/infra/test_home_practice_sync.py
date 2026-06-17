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


# ── Idempotency (T1, twin of E3 benchmark sync) ──────────────────────────────


async def _link_cohort_artifact(conn, artifact_id, snapshot_id) -> None:
    """Wire a cohort_artifact → cohorts_resource (snapshot) link.

    Mirrors what ``update_cohort_artifact`` writes (``cohort_cohorts_junction``)
    — the join the idempotency clear walks to find this cohort's every prior
    snapshot.
    """
    await conn.execute(
        "INSERT INTO cohort_artifact (id, active, generated, mcp) "
        "VALUES ($1, true, false, false) ON CONFLICT (id) DO NOTHING",
        artifact_id,
    )
    await conn.execute(
        "INSERT INTO cohort_cohorts_junction (cohort_id, cohorts_id, active, generated) "
        "VALUES ($1, $2, true, false) "
        "ON CONFLICT ON CONSTRAINT cohort_cohorts_junction_pkey DO NOTHING",
        artifact_id,
        snapshot_id,
    )


async def _active_practice_count_for_snapshot(pool, snapshot_id) -> int:
    """Count active generated practice_entry rows linked to a snapshot."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            SELECT count(DISTINCT pe.id)
            FROM practice_entry pe
            JOIN practice_cohorts_connection pcc ON pcc.practice_id = pe.id
            WHERE pcc.cohorts_id = $1
              AND pcc.active = true
              AND pe.active = true
              AND pe.generated = true
            """,
            snapshot_id,
        )


async def _active_chat_count_for_snapshot(pool, snapshot_id) -> int:
    """Count active generated chat_entry rows reachable from a snapshot's practices."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            SELECT count(DISTINCT ce.id)
            FROM chat_entry ce
            JOIN practice_chat_entry pce ON pce.chat_id = ce.id AND pce.active = true
            JOIN practice_entry pe ON pe.id = pce.practice_id AND pe.active = true
            JOIN practice_cohorts_connection pcc
              ON pcc.practice_id = pe.id AND pcc.active = true
            WHERE pcc.cohorts_id = $1
              AND ce.active = true
              AND ce.generated = true
            """,
            snapshot_id,
        )


async def test_sync_is_idempotent_no_duplicate_trees_on_rerun(
    pool, redis_client, sync_fixture
):
    """A second sync for the same cohort REPLACES — it must not append duplicates.

    Before the T1 fix (insert-only, no clear) a second ``/cohort/update`` ran
    this again and appended a fresh full practice+chat tree → N edits gave N
    active trees. With the scoped clear-before-recreate, re-running leaves
    exactly one active generated tree for the cohort's snapshot.
    """
    from uuid import uuid4

    artifact_id = uuid4()
    snapshot_id = sync_fixture["cohort_id"]
    async with pool.acquire() as conn:
        await _link_cohort_artifact(conn, artifact_id, snapshot_id)

    kwargs = dict(
        pool=pool,
        cohorts_resource_id=snapshot_id,
        simulation_ids=[sync_fixture["simulation_id"]],
        simulation_position_ids=[],
        simulation_availability_ids=[],
        department_ids=[],
        profile_ids=[sync_fixture["profile_id"]],
        profile_persona_ids=[],
        cohort_artifact_id=artifact_id,
    )

    await sync_home_practice_entries(**kwargs)
    assert await _active_practice_count_for_snapshot(pool, snapshot_id) == 1
    assert await _active_chat_count_for_snapshot(pool, snapshot_id) == 1

    # Second run — must replace, not append.
    await sync_home_practice_entries(**kwargs)
    assert await _active_practice_count_for_snapshot(pool, snapshot_id) == 1, (
        "second sync appended a duplicate active practice tree (non-idempotent)"
    )
    assert await _active_chat_count_for_snapshot(pool, snapshot_id) == 1, (
        "second sync appended a duplicate active chat tree (non-idempotent)"
    )

    # And a third, for good measure.
    await sync_home_practice_entries(**kwargs)
    assert await _active_practice_count_for_snapshot(pool, snapshot_id) == 1
    assert await _active_chat_count_for_snapshot(pool, snapshot_id) == 1


async def test_sync_clear_is_scoped_to_this_cohort(pool, redis_client, sync_fixture):
    """Re-running one cohort's sync must NOT deactivate another cohort's tree."""
    from uuid import uuid4

    from app.tools.resources.cohorts.create import create_cohort

    artifact_a = uuid4()
    snapshot_a = sync_fixture["cohort_id"]

    # A second, independent cohort sharing the same simulation/scenario graph.
    async with pool.acquire() as conn:
        other_snapshot = await create_cohort(conn, redis_client)
        artifact_b = uuid4()
        await _link_cohort_artifact(conn, artifact_a, snapshot_a)
        await _link_cohort_artifact(conn, artifact_b, other_snapshot.id)

    base = dict(
        pool=pool,
        simulation_ids=[sync_fixture["simulation_id"]],
        simulation_position_ids=[],
        simulation_availability_ids=[],
        department_ids=[],
        profile_ids=[sync_fixture["profile_id"]],
        profile_persona_ids=[],
    )

    await sync_home_practice_entries(
        cohorts_resource_id=snapshot_a, cohort_artifact_id=artifact_a, **base
    )
    await sync_home_practice_entries(
        cohorts_resource_id=other_snapshot.id, cohort_artifact_id=artifact_b, **base
    )

    assert await _active_practice_count_for_snapshot(pool, snapshot_a) == 1
    assert await _active_practice_count_for_snapshot(pool, other_snapshot.id) == 1

    # Re-run cohort A only — cohort B's tree must survive untouched.
    await sync_home_practice_entries(
        cohorts_resource_id=snapshot_a, cohort_artifact_id=artifact_a, **base
    )
    assert await _active_practice_count_for_snapshot(pool, snapshot_a) == 1
    assert await _active_practice_count_for_snapshot(pool, other_snapshot.id) == 1, (
        "re-running cohort A's sync wrongly deactivated cohort B's tree "
        "(clear not scoped to the acting cohort)"
    )


async def test_sync_clear_rolls_back_with_recreate_on_failure(
    pool, redis_client, sync_fixture, monkeypatch
):
    """The clear and the recreate are one atomic unit.

    If the recreate fails mid-way, the clear of the prior tree must roll back
    too — the cohort keeps its old (working) scaffold rather than ending up
    with the old one deactivated and no replacement (a silently empty cohort).
    """
    from uuid import uuid4

    artifact_id = uuid4()
    snapshot_id = sync_fixture["cohort_id"]
    async with pool.acquire() as conn:
        await _link_cohort_artifact(conn, artifact_id, snapshot_id)

    kwargs = dict(
        pool=pool,
        cohorts_resource_id=snapshot_id,
        simulation_ids=[sync_fixture["simulation_id"]],
        simulation_position_ids=[],
        simulation_availability_ids=[],
        department_ids=[],
        profile_ids=[sync_fixture["profile_id"]],
        profile_persona_ids=[],
        cohort_artifact_id=artifact_id,
    )

    # Seed a working prior tree.
    await sync_home_practice_entries(**kwargs)
    assert await _active_practice_count_for_snapshot(pool, snapshot_id) == 1

    # Inject a failure during the recreate (after the clear has run inside the
    # same transaction).
    import app.tools.entries.chat.create as chat_create_mod

    async def _boom(*args, **kwargs):
        raise RuntimeError("injected failure during recreate")

    monkeypatch.setattr(chat_create_mod, "create_chat", _boom)

    with pytest.raises(RuntimeError, match="injected failure"):
        await sync_home_practice_entries(**kwargs)

    # The prior tree must still be active — the clear rolled back with the
    # failed recreate (not deactivated-with-no-replacement).
    assert await _active_practice_count_for_snapshot(pool, snapshot_id) == 1, (
        "the prior tree was deactivated but the recreate failed — the clear "
        "did not roll back atomically with the recreate"
    )


# ── HC3 (report-21): soft-delete must invalidate the hedged per-id cache ──────


async def _prior_tree_ids(pool, snapshot_id):
    """The active generated practice + chat ids currently linked to a snapshot."""
    async with pool.acquire() as conn:
        practice_rows = await conn.fetch(
            """
            SELECT DISTINCT pe.id
            FROM practice_entry pe
            JOIN practice_cohorts_connection pcc ON pcc.practice_id = pe.id
            WHERE pcc.cohorts_id = $1
              AND pcc.active = true
              AND pe.active = true
              AND pe.generated = true
            """,
            snapshot_id,
        )
        chat_rows = await conn.fetch(
            """
            SELECT DISTINCT ce.id
            FROM chat_entry ce
            JOIN practice_chat_entry pce ON pce.chat_id = ce.id AND pce.active = true
            JOIN practice_entry pe ON pe.id = pce.practice_id AND pe.active = true
            JOIN practice_cohorts_connection pcc
              ON pcc.practice_id = pe.id AND pcc.active = true
            WHERE pcc.cohorts_id = $1
              AND ce.active = true
              AND ce.generated = true
            """,
            snapshot_id,
        )
    return [r["id"] for r in practice_rows], [r["id"] for r in chat_rows]


async def test_sync_soft_delete_invalidates_hedged_cache(
    pool, redis_client, sync_fixture
):
    """HC3: re-syncing soft-deletes the prior cohort's home/practice/chat rows;
    those rows are served from the per-id hedged cache (``entry:<ns>:<id>``), so
    the soft-delete MUST bust their cache keys. Before the fix the deactivation
    issued ZERO invalidate_row calls, so a GET right after a re-sync still
    returned the stale (now-inactive) scaffold from cache for the TTL.

    Set-up: run sync once, find the prior practice + chat ids, warm their per-id
    cache keys (mirrors what create/get write-backs would leave live), then
    re-sync (which deactivates that prior tree) and assert the prior ids' cache
    keys are gone.
    """
    from uuid import uuid4

    from app.utils.cache.hedged_row import read_back_row, write_back_row

    artifact_id = uuid4()
    snapshot_id = sync_fixture["cohort_id"]
    async with pool.acquire() as conn:
        await _link_cohort_artifact(conn, artifact_id, snapshot_id)

    kwargs = dict(
        pool=pool,
        cohorts_resource_id=snapshot_id,
        simulation_ids=[sync_fixture["simulation_id"]],
        simulation_position_ids=[],
        simulation_availability_ids=[],
        department_ids=[],
        profile_ids=[sync_fixture["profile_id"]],
        profile_persona_ids=[],
        cohort_artifact_id=artifact_id,
    )

    # First sync builds a tree (sync_fixture's simulation is practice=True).
    await sync_home_practice_entries(**kwargs)
    prior_practice_ids, prior_chat_ids = await _prior_tree_ids(pool, snapshot_id)
    assert prior_practice_ids, "expected at least one practice row from the sync"
    assert prior_chat_ids, "expected at least one chat row from the sync"

    # Warm the per-id hedged cache for every prior row, in the exact namespaces
    # the GET/search consumers read (practice→"practice", chat→"chat").
    for pid in prior_practice_ids:
        await write_back_row(redis_client, "practice", pid, {"id": str(pid)})
    for cid in prior_chat_ids:
        await write_back_row(redis_client, "chat", cid, {"id": str(cid)})
    # Sanity: the cache is warm before the re-sync.
    for pid in prior_practice_ids:
        assert await read_back_row(redis_client, "practice", pid) is not None
    for cid in prior_chat_ids:
        assert await read_back_row(redis_client, "chat", cid) is not None

    # Re-sync: deactivates the prior tree (active=false) AND must bust its cache.
    await sync_home_practice_entries(**kwargs)

    for pid in prior_practice_ids:
        assert await read_back_row(redis_client, "practice", pid) is None, (
            f"soft-deleted practice row {pid} still served from the hedged "
            "cache — sync did not invalidate its per-id key (HC3)"
        )
    for cid in prior_chat_ids:
        assert await read_back_row(redis_client, "chat", cid) is None, (
            f"soft-deleted chat row {cid} still served from the hedged cache — "
            "sync did not invalidate its per-id key (HC3)"
        )


async def _prior_bridge_ids(pool, snapshot_id):
    """Active generated practice_chat (+ home_chat) BRIDGE ids for a snapshot."""
    async with pool.acquire() as conn:
        practice_bridge = await conn.fetch(
            """
            SELECT DISTINCT pce.id
            FROM practice_chat_entry pce
            JOIN practice_entry pe ON pe.id = pce.practice_id AND pe.active = true
            JOIN practice_cohorts_connection pcc
              ON pcc.practice_id = pe.id AND pcc.active = true
            WHERE pcc.cohorts_id = $1 AND pce.active = true
            """,
            snapshot_id,
        )
        home_bridge = await conn.fetch(
            """
            SELECT DISTINCT hce.id
            FROM home_chat_entry hce
            JOIN home_entry he ON he.id = hce.home_id AND he.active = true
            JOIN home_cohorts_connection hcc
              ON hcc.home_id = he.id AND hcc.active = true
            WHERE hcc.cohorts_id = $1 AND hce.active = true
            """,
            snapshot_id,
        )
    return [r["id"] for r in practice_bridge], [r["id"] for r in home_bridge]


async def test_sync_soft_delete_invalidates_bridge_caches(
    pool, redis_client, sync_fixture
):
    """HC3-INCOMPLETE (report-22): the re-sync also soft-deletes the BRIDGE rows
    (practice_chat / home_chat), which are served from their own per-id hedged
    caches. #390 collected the bridge arms with ``RETURNING 1`` (not their id),
    so those namespaces were never invalidated and the stale active=true bridge
    rows were served for the TTL. The bridge ids must now be busted too."""
    from uuid import uuid4

    from app.utils.cache.hedged_row import read_back_row, write_back_row

    artifact_id = uuid4()
    snapshot_id = sync_fixture["cohort_id"]
    async with pool.acquire() as conn:
        await _link_cohort_artifact(conn, artifact_id, snapshot_id)

    kwargs = dict(
        pool=pool,
        cohorts_resource_id=snapshot_id,
        simulation_ids=[sync_fixture["simulation_id"]],
        simulation_position_ids=[],
        simulation_availability_ids=[],
        department_ids=[],
        profile_ids=[sync_fixture["profile_id"]],
        profile_persona_ids=[],
        cohort_artifact_id=artifact_id,
    )

    await sync_home_practice_entries(**kwargs)
    practice_bridge_ids, home_bridge_ids = await _prior_bridge_ids(pool, snapshot_id)
    # The fixture's simulation is practice=True, so practice_chat bridges exist.
    assert practice_bridge_ids, "expected at least one practice_chat bridge row"

    for bid in practice_bridge_ids:
        await write_back_row(redis_client, "practice_chat", bid, {"id": str(bid)})
    for bid in home_bridge_ids:
        await write_back_row(redis_client, "home_chat", bid, {"id": str(bid)})
    for bid in practice_bridge_ids:
        assert await read_back_row(redis_client, "practice_chat", bid) is not None

    await sync_home_practice_entries(**kwargs)

    for bid in practice_bridge_ids:
        assert await read_back_row(redis_client, "practice_chat", bid) is None, (
            f"soft-deleted practice_chat bridge {bid} still served from cache — "
            "the bridge namespace was not invalidated (HC3-INCOMPLETE)"
        )
    for bid in home_bridge_ids:
        assert await read_back_row(redis_client, "home_chat", bid) is None, (
            f"soft-deleted home_chat bridge {bid} still served from cache — "
            "the bridge namespace was not invalidated (HC3-INCOMPLETE)"
        )
