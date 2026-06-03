"""Tests for auth update — profile check, permission check."""

from uuid import uuid4
import pytest
from app.infra.auth.update import update_auth_impl
from app.infra.auth.types import UpdateAuthApiRequest, UpdateAuthItem

pytestmark = pytest.mark.asyncio


async def test_update_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.auth.update.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await update_auth_impl(None, None, profile_id=uuid4(), request=UpdateAuthApiRequest(auths=[UpdateAuthItem(id=uuid4())]))
    assert exc_info.value.status_code == 401


async def test_update_raises_400_for_no_items(monkeypatch):
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
    monkeypatch.setattr("app.infra.auth.update.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await update_auth_impl(
            None, None, profile_id=uuid4(),
            request=UpdateAuthApiRequest(auths=[]),
        )
    assert exc_info.value.status_code == 400


async def test_update_detail_mentions_sign_in(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.auth.update.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await update_auth_impl(None, None, profile_id=uuid4(), request=UpdateAuthApiRequest(auths=[UpdateAuthItem(id=uuid4())]))
    assert "sign in" in exc_info.value.detail.lower()
