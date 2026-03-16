"""Integration tests for infra.model_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.model.context import resolve_model_context
from app.tools.artifacts.model.create import create_model
from app.tools.artifacts.model.update import update_model

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        model = await create_model(conn)
        await update_model(conn, model.id, active=False)

    result = await resolve_model_context(
        pool,
        redis_client,
        model_id=model.id,
        group_id=uuid4(),
    )

    assert result.active is False
