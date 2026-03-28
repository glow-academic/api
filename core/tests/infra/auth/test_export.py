"""Tests for auth export — profile check, empty export."""

from dataclasses import dataclass
from uuid import uuid4
import pytest
from app.infra.auth.export import export_auth_impl

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


async def test_export_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.auth.export.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await export_auth_impl(_Pool(), None, profile_id=uuid4())
    assert exc_info.value.status_code == 401


async def test_export_returns_empty_for_no_artifacts(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return _P(profiles_id=uuid4())
    async def mock_search(conn, **kw):
        return ([], 0)
    monkeypatch.setattr("app.infra.auth.export.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.auth.export.search_auths", mock_search)
    result = await export_auth_impl(_Pool(), None, profile_id=uuid4())
    assert result.row_count == 0


async def test_export_detail_mentions_sign_in(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.auth.export.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await export_auth_impl(_Pool(), None, profile_id=uuid4())
    assert "sign in" in exc_info.value.detail.lower()
