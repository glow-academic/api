"""Tests for provider update — profile check, permission check."""

from uuid import uuid4
import pytest
from app.infra.provider.update import update_provider_impl

pytestmark = pytest.mark.asyncio


async def test_update_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.provider.update.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await update_provider_impl(None, None, profile_id=uuid4(), items=[])
    assert exc_info.value.status_code == 401


async def test_update_returns_empty_results_for_no_items(monkeypatch):
    from dataclasses import dataclass
    @dataclass
    class P:
        profiles_id: object = None
        role: str = "superadmin"
        name: str = "U"
        group_id: object = None
        department_ids: list = None
        role_level: int = 0
        role_permissions: list = None
    async def mock_resolve(pool, pid, redis, **kw):
        return P(profiles_id=uuid4())
    async def mock_invalidate(tags, redis=None):
        pass
    async def mock_keycloak(**kw):
        pass
    monkeypatch.setattr("app.infra.provider.update.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.provider.update.invalidate_tags", mock_invalidate)
    monkeypatch.setattr("app.infra.provider.update.perform_keycloak_sync", mock_keycloak)
    result = await update_provider_impl(None, None, profile_id=uuid4(), items=[])
    assert hasattr(result, "results")
    assert len(result.results) == 0


async def test_update_detail_mentions_sign_in(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.provider.update.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await update_provider_impl(None, None, profile_id=uuid4(), items=[])
    assert "sign in" in exc_info.value.detail.lower()
