"""Tests for get_table_info."""

import pytest

from app.infra.docs.get_table_info import get_table_info

pytestmark = pytest.mark.asyncio


async def test_returns_table_info(conn):
    result = await get_table_info(conn, "sessions_entry")

    assert result is not None
    assert result.name == "sessions_entry"
    assert len(result.columns) > 0


async def test_columns_include_id(conn):
    result = await get_table_info(conn, "sessions_entry")

    assert result is not None
    col_names = [c.name for c in result.columns]
    assert "id" in col_names


async def test_columns_have_types(conn):
    result = await get_table_info(conn, "sessions_entry")

    assert result is not None
    for col in result.columns:
        assert len(col.type) > 0


async def test_returns_none_for_missing(conn):
    result = await get_table_info(conn, "nonexistent_table")

    assert result is None
