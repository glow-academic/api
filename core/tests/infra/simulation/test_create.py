"""Tests for simulation create — profile check, permission check."""

from uuid import uuid4
import pytest
from app.infra.simulation.create import create_simulation_impl

pytestmark = pytest.mark.asyncio


async def test_create_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.simulation.create.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await create_simulation_impl(None, None, profile_id=uuid4(), items=[])
    assert exc_info.value.status_code == 401


async def test_create_raises_403_for_unauthorized_role(monkeypatch):
    from dataclasses import dataclass
    @dataclass
    class P:
        profiles_id: object = None
        role: str = "member"
        name: str = "U"
        group_id: object = None
        department_ids: list = None
    async def mock_resolve(pool, pid, redis, **kw):
        return P(profiles_id=uuid4())
    monkeypatch.setattr("app.infra.simulation.create.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await create_simulation_impl(None, None, profile_id=uuid4(), items=[])
    assert exc_info.value.status_code == 403


async def test_create_detail_mentions_sign_in(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.simulation.create.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await create_simulation_impl(None, None, profile_id=uuid4(), items=[])
    assert "sign in" in exc_info.value.detail.lower()
