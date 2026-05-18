"""Tests for get_profile_drafts_docs."""

import pytest

from app.tools.entries.profile_drafts.docs import get_profile_drafts_docs

pytestmark = pytest.mark.asyncio


async def test_returns_docs_response(conn):
    result = await get_profile_drafts_docs(conn)

    assert result.name == "profile_drafts"
    assert result.type == "entry"
    assert len(result.description) > 0


async def test_includes_materialized_view(conn):
    result = await get_profile_drafts_docs(conn)

    assert result.materialized_view is not None
    assert result.materialized_view.name == "profile_drafts_mv"
    assert len(result.materialized_view.definition) > 0
    assert len(result.materialized_view.columns) > 0


async def test_includes_source_tables(conn):
    result = await get_profile_drafts_docs(conn)

    table_names = [t.name for t in result.tables]
    assert "profile_drafts_entry" in table_names
    assert "profile_drafts_profiles_connection" in table_names
    assert "profile_drafts_names_connection" in table_names


async def test_includes_all_operations(conn):
    result = await get_profile_drafts_docs(conn)

    op_names = [op.name for op in result.operations]
    assert "create_profile_draft" in op_names
    assert "refresh_profile_drafts" in op_names
    assert "get_profile_drafts" in op_names
    assert "search_profile_drafts" in op_names


async def test_create_operation_has_params(conn):
    result = await get_profile_drafts_docs(conn)

    create_op = next(
        op for op in result.operations if op.name == "create_profile_draft"
    )
    param_names = [p.name for p in create_op.params]
    assert "group_id" in param_names
    assert "session_id" in param_names


async def test_search_operation_has_filters(conn):
    result = await get_profile_drafts_docs(conn)

    search_op = next(
        op for op in result.operations if op.name == "search_profile_drafts"
    )
    param_names = [p.name for p in search_op.params]
    assert "group_ids" in param_names
    assert "session_ids" in param_names
    assert "profile_ids" in param_names
    assert "date_from" in param_names
    assert "date_to" in param_names
    assert "mcp" in param_names
