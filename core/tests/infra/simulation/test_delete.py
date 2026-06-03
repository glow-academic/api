"""Tests for simulation delete — profile check, 404 for missing."""

from uuid import uuid4
import pytest
from app.infra.simulation.delete import delete_simulation_impl

pytestmark = pytest.mark.asyncio


async def test_delete_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.simulation.delete.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await delete_simulation_impl(None, None, profile_id=uuid4(), ids=[uuid4()])
    assert exc_info.value.status_code == 401


async def test_delete_detail_mentions_sign_in(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.simulation.delete.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await delete_simulation_impl(None, None, profile_id=uuid4(), ids=[uuid4()])
    assert "sign in" in exc_info.value.detail.lower()


async def test_delete_is_async_callable():
    import asyncio
    assert asyncio.iscoroutinefunction(delete_simulation_impl)
