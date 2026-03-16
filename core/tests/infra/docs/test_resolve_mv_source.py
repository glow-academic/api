"""Tests for resolve_mv_source."""

import pytest

from app.infra.docs.resolve_mv_source import resolve_mv_source

pytestmark = pytest.mark.asyncio


async def test_returns_mv_name_when_not_bypassed(conn):
    result = await resolve_mv_source(conn, "sessions_mv", bypass_mv=False)

    assert result == "sessions_mv"


async def test_returns_subquery_when_bypassed(conn):
    result = await resolve_mv_source(conn, "sessions_mv", bypass_mv=True)

    assert result.startswith("(")
    assert result.endswith(") mv")
    assert "sessions_entry" in result


async def test_raises_for_missing_mv_when_bypassed(conn):
    with pytest.raises(ValueError, match="not found"):
        await resolve_mv_source(conn, "nonexistent_mv", bypass_mv=True)
