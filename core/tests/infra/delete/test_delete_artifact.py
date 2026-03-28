"""Tests for delete_artifacts."""
import pytest
from app.infra.delete.delete_artifact import delete_artifacts
pytestmark = pytest.mark.asyncio

async def test_delete_empty_ids_returns_empty(conn):
    result = await delete_artifacts(conn, table="profile_artifact", ids=[], soft=False)
    assert result == []

async def test_delete_nonexistent_returns_empty(conn):
    from uuid import uuid4
    result = await delete_artifacts(conn, table="profile_artifact", ids=[uuid4()], soft=False)
    assert result == []

async def test_soft_delete_nonexistent_returns_empty(conn):
    from uuid import uuid4
    result = await delete_artifacts(conn, table="profile_artifact", ids=[uuid4()], soft=True)
    assert result == []
