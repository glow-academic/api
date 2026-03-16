"""Tests for create_email."""

import pytest

from app.tools.resources.emails.create import create_email
from app.tools.resources.emails.get import get_emails

pytestmark = pytest.mark.asyncio


async def test_creates_new_email(conn, redis_client):
    result = await create_email(conn, "new@example.com", redis_client)

    assert result.email == "new@example.com"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_email(conn, "visible@example.com", redis_client)

    items = await get_emails(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].email == "visible@example.com"


async def test_returns_existing_on_conflict(conn, redis_client):
    first = await create_email(conn, "duplicate@example.com", redis_client)
    second = await create_email(conn, "duplicate@example.com", redis_client)

    assert first.id == second.id
    assert second.email == "duplicate@example.com"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_email(conn, "mcp@example.com", redis_client, mcp=True)

    assert result.mcp is True
    assert result.generated is True
