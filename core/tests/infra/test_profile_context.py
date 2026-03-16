"""Integration tests for infra.profile_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.profile.context import resolve_profile_context
from app.tools.artifacts.profile.create import create_profile
from app.tools.artifacts.profile.update import update_profile

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        profile = await create_profile(conn)
        await update_profile(conn, profile.id, active=False)

    result = await resolve_profile_context(
        pool,
        redis_client,
        profile_id=profile.id,
        group_id=uuid4(),
    )

    assert result.active is False
