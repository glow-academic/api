"""Integration tests for infra.department_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.department.context import resolve_department_context
from app.tools.artifacts.department.create import create_department
from app.tools.artifacts.department.update import update_department

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        department = await create_department(conn)
        await update_department(conn, department.id, active=False)

    result = await resolve_department_context(
        pool,
        redis_client,
        department_id=department.id,
        group_id=uuid4(),
    )

    assert result.active is False
