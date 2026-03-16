"""Tests for create_artifact."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.artifacts.create import create_artifact
from app.tools.resources.artifacts.get import get_artifacts

pytestmark = pytest.mark.asyncio


async def test_creates_new_artifact(conn, redis_client):
    result = await create_artifact(conn, f"test-artifact-{unique_tag()}", redis_client)

    assert result.artifact is not None
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_artifact(
        conn, f"visible-artifact-{unique_tag()}", redis_client
    )

    items = await get_artifacts(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].artifact == result.artifact


async def test_returns_existing_on_conflict(conn, redis_client):
    name = f"duplicate-artifact-{unique_tag()}"
    first = await create_artifact(conn, name, redis_client)
    second = await create_artifact(conn, name, redis_client)

    assert first.id == second.id
    assert second.artifact == name


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_artifact(
        conn, f"mcp-artifact-{unique_tag()}", redis_client, mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
