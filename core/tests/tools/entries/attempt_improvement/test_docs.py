"""Tests for get_attempt_improvement_docs."""

import pytest

from app.tools.entries.attempt_improvement.docs import (
    get_attempt_improvement_docs,
)

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_attempt_improvement_docs(conn)

    assert result.name == "attempt_improvement"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_materialized_view(conn):
    result = await get_attempt_improvement_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "attempt_improvement_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_source_tables(conn):
    result = await get_attempt_improvement_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "attempt_improvement_entry" in table_names


async def test_includes_all_operations(conn):
    result = await get_attempt_improvement_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_attempt_improvement" in op_names
    assert "refresh_attempt_improvement" in op_names
    assert "get_attempt_improvements" in op_names
    assert "search_attempt_improvements" in op_names


async def test_create_operation_has_params(conn):
    result = await get_attempt_improvement_docs(conn)

    create_op = next(
        op for op in result.operations if op.name == "create_attempt_improvement"
    )
    param_names = [p.name for p in create_op.params]
    assert "grade_id" in param_names
    assert "message_id" in param_names
    assert "call_id" in param_names
    assert "name" in param_names
    assert "description" in param_names
