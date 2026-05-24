"""Integration tests for infra.parameter_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.parameter.context import resolve_parameter_context
from app.tools.artifacts.parameter.create import create_parameter
from app.tools.artifacts.parameter.update import update_parameter

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        parameter = await create_parameter(conn)
        await update_parameter(conn, parameter.id, active=False)

    result = await resolve_parameter_context(
        pool,
        redis_client,
        parameter_id=parameter.id,
        group_id=uuid4(),
    )

    assert result.active is False
