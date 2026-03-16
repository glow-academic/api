"""Tests for create_role."""

import pytest

from app.tools.resources.roles.create import create_role
from app.tools.resources.roles.get import get_roles

pytestmark = pytest.mark.asyncio


async def test_creates_new_role(conn, redis_client):
    result = await create_role(
        conn, "admin", redis_client, name="New Admin Role", description="desc"
    )

    assert result.role == "admin"
    assert result.name == "New Admin Role"
    assert result.description == "desc"
    assert result.icon_id is None
    assert result.color_id is None
    assert result.artifacts == []
    assert result.active is True
    assert result.mcp is False


async def test_creates_role_with_artifacts(conn, redis_client):
    result = await create_role(
        conn,
        "instructional",
        redis_client,
        name="Artifact Role",
        artifacts=["persona", "scenario"],
    )

    assert result.artifacts == ["persona", "scenario"]


async def test_visible_via_get(conn, redis_client):
    result = await create_role(conn, "guest", redis_client, name="Visible Guest Role")

    items = await get_roles(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].role == "guest"
    assert items[0].name == "Visible Guest Role"


async def test_returns_existing_on_conflict(conn, redis_client):
    first = await create_role(conn, "member", redis_client, name="Dup Role")
    second = await create_role(conn, "member", redis_client, name="Dup Role")

    assert first.id == second.id
    assert second.role == "member"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_role(
        conn, "instructional", redis_client, name="MCP Role", mcp=True
    )

    assert result.mcp is True
    assert result.generated is True
