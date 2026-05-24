"""Integration tests for infra.auth_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.auth.context import resolve_auth_context
from app.tools.artifacts.auth.create import create_auth
from app.tools.artifacts.auth.update import update_auth

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        auth = await create_auth(conn)
        await update_auth(conn, auth.id, active=False)

    result = await resolve_auth_context(
        pool,
        redis_client,
        auth_id=auth.id,
        group_id=uuid4(),
    )

    assert result.active is False
