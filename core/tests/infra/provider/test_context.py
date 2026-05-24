"""Integration tests for infra.provider_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.provider.context import resolve_provider_context
from app.tools.artifacts.provider.create import create_provider
from app.tools.artifacts.provider.update import update_provider

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        provider = await create_provider(conn)
        await update_provider(conn, provider.id, active=False)

    result = await resolve_provider_context(
        pool,
        redis_client,
        provider_id=provider.id,
        group_id=uuid4(),
    )

    assert result.active is False
