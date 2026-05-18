"""Tests for get_message_uploads_docs."""

import pytest

from app.tools.entries.message_uploads.docs import get_message_uploads_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_message_uploads_docs(conn)

    assert result.name == "message_uploads"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_materialized_view(conn):
    result = await get_message_uploads_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "message_uploads_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_source_tables(conn):
    result = await get_message_uploads_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "message_uploads_entry" in table_names


async def test_includes_all_operations(conn):
    result = await get_message_uploads_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_message_upload" in op_names
    assert "refresh_message_uploads" in op_names
    assert "get_message_upload" in op_names
    assert "search_message_uploads" in op_names


async def test_create_operation_has_params(conn):
    result = await get_message_uploads_docs(conn)

    create_op = next(
        op for op in result.operations if op.name == "create_message_upload"
    )
    param_names = [p.name for p in create_op.params]
    assert "message_id" in param_names
    assert "upload_id" in param_names
    assert "session_id" in param_names
    assert "mcp" in param_names
