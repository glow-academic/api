"""Integration tests for infra.cohort.context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.cohort.context import resolve_cohort_context
from app.tools.artifacts.cohort.create import create_cohort
from app.tools.artifacts.cohort.update import update_cohort

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        cohort = await create_cohort(conn)
        await update_cohort(conn, cohort.id, active=False)

    result = await resolve_cohort_context(
        pool,
        redis_client,
        cohort_id=cohort.id,
        group_id=uuid4(),
    )

    assert result.active is False
