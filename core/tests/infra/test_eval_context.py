"""Integration tests for infra.eval_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.eval.context import resolve_eval_context
from app.tools.artifacts.eval.create import create_eval
from app.tools.artifacts.eval.update import update_eval

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        eval_artifact = await create_eval(conn)
        await update_eval(conn, eval_artifact.id, active=False)

    result = await resolve_eval_context(
        pool,
        redis_client,
        eval_id=eval_artifact.id,
        group_id=uuid4(),
    )

    assert result.active is False
