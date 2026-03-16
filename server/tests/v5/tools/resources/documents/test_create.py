"""Tests for create_document."""

import pytest

from app.tools.resources.documents.create import create_document
from app.tools.resources.documents.get import get_documents

pytestmark = pytest.mark.asyncio


async def test_creates_new_document(conn, redis_client):
    result = await create_document(
        conn, redis_client, name="test-doc", description="desc"
    )

    assert result.name == "test-doc"
    assert result.description == "desc"
    assert result.active is True
    assert result.mcp is False


async def test_visible_via_get(conn, redis_client):
    result = await create_document(conn, redis_client, name="test-doc-visible")

    items = await get_documents(conn, [result.id], redis_client, bypass_cache=True)

    assert len(items) == 1
    assert items[0].id == result.id
    assert items[0].name == "test-doc-visible"


async def test_creates_second_row_with_same_name(conn, redis_client):
    first = await create_document(conn, redis_client, name="duplicate-doc")
    second = await create_document(conn, redis_client, name="duplicate-doc")

    assert first.id != second.id
    assert second.name == "duplicate-doc"


async def test_sets_mcp_flag(conn, redis_client):
    result = await create_document(conn, redis_client, name="mcp-doc", mcp=True)

    assert result.mcp is True
    assert result.generated is True
