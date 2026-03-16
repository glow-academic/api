"""Integration tests for infra.simulation_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.simulation.context import resolve_simulation_context
from app.tools.artifacts.simulation.create import create_simulation
from app.tools.artifacts.simulation.update import update_simulation

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        simulation = await create_simulation(conn)
        await update_simulation(conn, simulation.id, active=False)

    result = await resolve_simulation_context(
        pool,
        redis_client,
        simulation_id=simulation.id,
        group_id=uuid4(),
    )

    assert result.active is False
