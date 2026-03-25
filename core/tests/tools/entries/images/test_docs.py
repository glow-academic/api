"""Tests for get_images_docs."""

import pytest

from app.tools.entries.images.docs import get_images_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_images_docs(conn)

    assert result.name == "images"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_no_materialized_view(conn):
    result = await get_images_docs(conn)

    assert result.materialized_view is None


async def test_includes_source_tables(conn):
    result = await get_images_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "images_entry" in table_names


async def test_includes_all_operations(conn):
    result = await get_images_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_image" in op_names
    assert "get_image" in op_names
    assert "search_images" in op_names


async def test_create_operation_has_params(conn):
    result = await get_images_docs(conn)

    create_op = next(op for op in result.operations if op.name == "create_image")
    param_names = [p.name for p in create_op.params]
    assert "session_id" in param_names
