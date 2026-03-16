"""Integration tests for infra.field_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.field.context import resolve_field_context
from app.tools.artifacts.field.create import create_field
from app.tools.artifacts.field.update import update_field

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        field = await create_field(conn)
        await update_field(conn, field.id, active=False)

    result = await resolve_field_context(
        pool,
        redis_client,
        field_id=field.id,
        group_id=uuid4(),
    )

    assert result.active is False
