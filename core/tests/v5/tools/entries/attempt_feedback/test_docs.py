"""Tests for get_attempt_feedback_docs."""

import pytest

from app.tools.entries.attempt_feedback.docs import get_attempt_feedback_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_attempt_feedback_docs(conn)

    assert result.name == "attempt_feedback"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_materialized_view(conn):
    result = await get_attempt_feedback_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "attempt_feedback_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_source_tables(conn):
    result = await get_attempt_feedback_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "attempt_feedback_entry" in table_names
    assert "feedbacks_standards_connection" in table_names


async def test_includes_all_operations(conn):
    result = await get_attempt_feedback_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_attempt_feedback" in op_names
    assert "refresh_attempt_feedback" in op_names
    assert "get_attempt_feedbacks" in op_names
    assert "search_attempt_feedback_entries" in op_names


async def test_create_operation_has_params(conn):
    result = await get_attempt_feedback_docs(conn)

    create_op = next(
        op for op in result.operations if op.name == "create_attempt_feedback"
    )
    param_names = [p.name for p in create_op.params]
    assert "grade_id" in param_names
    assert "call_id" in param_names
    assert "total" in param_names
    assert "feedback" in param_names
