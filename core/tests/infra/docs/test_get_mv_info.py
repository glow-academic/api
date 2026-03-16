"""Tests for get_mv_info."""

import pytest

from app.infra.docs.get_mv_info import get_mv_info

pytestmark = pytest.mark.asyncio


async def test_returns_mv_info(conn):
    result = await get_mv_info(conn, "sessions_mv")

    assert result is not None
    assert result.name == "sessions_mv"
    assert len(result.definition) > 0
    assert len(result.columns) > 0


async def test_columns_include_session_id(conn):
    result = await get_mv_info(conn, "sessions_mv")

    assert result is not None
    col_names = [c.name for c in result.columns]
    assert "session_id" in col_names


async def test_columns_have_types(conn):
    result = await get_mv_info(conn, "sessions_mv")

    assert result is not None
    for col in result.columns:
        assert len(col.type) > 0


async def test_returns_none_for_missing(conn):
    result = await get_mv_info(conn, "nonexistent_mv")

    assert result is None
