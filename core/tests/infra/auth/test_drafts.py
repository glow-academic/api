"""Tests for auth drafts list — profile check, ownership."""

from dataclasses import dataclass
from uuid import uuid4
import pytest
from app.infra.auth.drafts import list_auth_drafts_impl

pytestmark = pytest.mark.asyncio


@dataclass
class _P:
    profiles_id: object = None
    role: str = "superadmin"
    name: str = "U"
    group_id: object = None
    department_ids: list = None
    role_level: int = 0
    role_permissions: list = None


class _Ctx:
    async def __aenter__(self):
        return None
    async def __aexit__(self, *a):
        pass


class _Pool:
    def acquire(self):
        return _Ctx()


async def test_drafts_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.auth.drafts.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await list_auth_drafts_impl(_Pool(), None, profile_id=uuid4())
    assert exc_info.value.status_code == 401


async def test_drafts_returns_context_with_entries(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return _P(profiles_id=uuid4(), group_id=uuid4())
    async def mock_search(conn, profile_ids=None):
        return []
    monkeypatch.setattr("app.infra.auth.drafts.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.auth.drafts.search_auth_drafts", mock_search)
    result = await list_auth_drafts_impl(_Pool(), None, profile_id=uuid4())
    assert "drafts" in result.entries


async def test_drafts_passes_profile_ownership(monkeypatch):
    pid = uuid4()
    captured = []
    async def mock_resolve(pool, profile_id, redis, **kw):
        return _P(profiles_id=pid, group_id=uuid4())
    async def mock_search(conn, profile_ids=None):
        captured.extend(profile_ids or [])
        return []
    monkeypatch.setattr("app.infra.auth.drafts.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.auth.drafts.search_auth_drafts", mock_search)
    await list_auth_drafts_impl(_Pool(), None, profile_id=uuid4())
    assert pid in captured
