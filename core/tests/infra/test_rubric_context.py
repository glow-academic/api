"""Integration tests for infra.rubric_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.rubric.context import resolve_rubric_context
from app.tools.artifacts.rubric.create import create_rubric
from app.tools.artifacts.rubric.update import update_rubric

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        rubric = await create_rubric(conn)
        await update_rubric(conn, rubric.id, active=False)

    result = await resolve_rubric_context(
        pool,
        redis_client,
        rubric_id=rubric.id,
        group_id=uuid4(),
    )

    assert result.active is False
