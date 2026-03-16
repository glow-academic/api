"""Integration tests for infra.setting_context — real DB, no mocks."""

from uuid import uuid4

import pytest

from app.infra.setting.context import resolve_setting_context
from app.tools.artifacts.setting.create import create_setting
from app.tools.artifacts.setting.update import update_setting

pytestmark = pytest.mark.asyncio


async def test_inactive_artifact_returns_inactive_context(pool, redis_client):
    async with pool.acquire() as conn:
        setting = await create_setting(conn)
        await update_setting(conn, setting.id, active=False)

    result = await resolve_setting_context(
        pool,
        redis_client,
        setting_id=setting.id,
        group_id=uuid4(),
    )

    assert result.active is False
