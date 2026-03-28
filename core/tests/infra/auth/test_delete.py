"""Tests for auth delete — profile check, 404 for missing."""

from dataclasses import dataclass
from uuid import uuid4
import pytest
from app.infra.auth.delete import delete_auth_impl

pytestmark = pytest.mark.asyncio


@dataclass
class _P:
    profiles_id: object = None
    role: str = "superadmin"
    name: str = "U"
    group_id: object = None
    department_ids: list = None


class _Ctx:
    async def __aenter__(self):
        return None
    async def __aexit__(self, *a):
        pass


class _Pool:
    def acquire(self):
        return _Ctx()


async def test_delete_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.auth.delete.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await delete_auth_impl(_Pool(), None, profile_id=uuid4(), auth_ids=[uuid4()])
    assert exc_info.value.status_code == 401


async def test_delete_raises_404_for_nonexistent(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return _P(profiles_id=uuid4())
    from app.infra.auth.permissions_context import AuthPermissionsContext
    async def mock_perms(conn, auth_id):
        return AuthPermissionsContext(exists=False, department_ids=[], active_settings_count=0)
    monkeypatch.setattr("app.infra.auth.delete.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.auth.delete.resolve_auth_permissions_context", mock_perms)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await delete_auth_impl(_Pool(), None, profile_id=uuid4(), auth_ids=[uuid4()])
    assert exc_info.value.status_code == 404


async def test_delete_detail_mentions_sign_in(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.auth.delete.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await delete_auth_impl(_Pool(), None, profile_id=uuid4(), auth_ids=[uuid4()])
    assert "sign in" in exc_info.value.detail.lower()
