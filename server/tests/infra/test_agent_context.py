"""Integration tests for infra.agent.context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.agent.context import resolve_agent_context
from app.tools.artifacts.agent.create import create_agent
from app.tools.artifacts.agent.update import update_agent

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        agent = await create_agent(conn)
        await update_agent(conn, agent.id, active=False)

    result = await resolve_agent_context(
        pool,
        redis_client,
        agent_id=agent.id,
        group_id=uuid4(),
    )

    assert result.active is False
