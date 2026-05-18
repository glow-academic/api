"""Integration tests for infra.tool_artifact_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.tool.context import resolve_tool_artifact_context
from app.tools.artifacts.tool.create import create_tool
from app.tools.artifacts.tool.update import update_tool

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        tool = await create_tool(conn)
        await update_tool(conn, tool.id, active=False)

    result = await resolve_tool_artifact_context(
        pool,
        redis_client,
        tool_id=tool.id,
        group_id=uuid4(),
    )

    assert result.active is False
