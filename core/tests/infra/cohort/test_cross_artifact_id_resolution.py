"""Regression: cohort create/update resolves simulation/profile artifact IDs to resource IDs.

Clients (and ``/simulation/search`` / ``/profile/search``) surface *artifact*
IDs, but ``cohort_simulations_junction.simulations_id`` and
``cohort_profiles_junction.profiles_id`` are FK'd to ``simulations_resource`` /
``profiles_resource`` (the denormalized snapshot each artifact owns via its own
self-junction), and the cohort read side hydrates them back through the
``*_resource`` getters. Before the fix ``resolve_cohort_values`` passed the
artifact IDs straight into the junction → ForeignKeyViolationError → HTTP 500.

Mutation-verified against the real DB pool via black-box tools only (no raw SQL).
"""

from uuid import uuid4

import pytest

from app.infra.cohort.permissions_context import resolve_cohort_values
from app.infra.cohort.types import CreateCohortItem
from app.tools.artifacts.profile.create import (
    create_profile as create_profile_artifact,
)
from app.tools.artifacts.simulation.create import (
    create_simulation as create_simulation_artifact,
)
from app.tools.resources.profiles.create import (
    create_profile as create_profile_resource,
)
from app.tools.resources.simulations.create import (
    create_simulation as create_simulation_resource,
)

pytestmark = pytest.mark.asyncio


async def _seed_simulation(pool, redis_client) -> tuple:
    async with pool.acquire() as conn:
        resource = await create_simulation_resource(
            conn, redis_client, name=f"s-{uuid4().hex[:8]}"
        )
        artifact = await create_simulation_artifact(
            conn, simulation_ids=[resource.id]
        )
    return artifact.id, resource.id


async def _seed_profile(pool, redis_client) -> tuple:
    async with pool.acquire() as conn:
        resource = await create_profile_resource(
            conn, redis_client, name=f"pr-{uuid4().hex[:8]}"
        )
        artifact = await create_profile_artifact(conn, profile_ids=[resource.id])
    return artifact.id, resource.id


async def test_resolve_rewrites_simulation_profile_artifact_ids(pool, redis_client):
    sim_a, sim_r = await _seed_simulation(pool, redis_client)
    prof_a, prof_r = await _seed_profile(pool, redis_client)

    item = CreateCohortItem(
        name="cohort-xref",
        simulation_ids=[sim_a],
        profile_ids=[prof_a],
    )
    async with pool.acquire() as conn:
        errors = await resolve_cohort_values(conn, redis_client, item, is_create=True)

    assert errors == []
    assert item.simulation_ids == [sim_r] and sim_a not in item.simulation_ids
    assert item.profile_ids == [prof_r] and prof_a not in item.profile_ids


async def test_unknown_cohort_cross_artifact_ids_pass_through(pool, redis_client):
    s, p = uuid4(), uuid4()
    item = CreateCohortItem(name="cohort-xref-2", simulation_ids=[s], profile_ids=[p])
    async with pool.acquire() as conn:
        errors = await resolve_cohort_values(conn, redis_client, item, is_create=True)

    assert errors == []
    assert item.simulation_ids == [s]
    assert item.profile_ids == [p]
