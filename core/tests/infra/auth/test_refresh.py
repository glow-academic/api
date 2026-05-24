"""Tests for auth refresh — MV refresh + cache invalidation."""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.infra.auth.refresh import refresh_auth_impl

pytestmark = pytest.mark.asyncio


@dataclass
class _FakeProfile:
    profiles_id: object = None
    role: str = "superadmin"
    name: str = "Test User"
    group_id: object = None
    department_ids: list = None
    role_level: int = 0
    role_permissions: list = None


class _FakeConnCtx:
    async def __aenter__(self):
        return None
    async def __aexit__(self, *a):
        pass


class _FakePool:
    def acquire(self):
        return _FakeConnCtx()


async def test_refresh_returns_success_with_tags(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return _FakeProfile(profiles_id=uuid4())

    refresh_called = []

    async def mock_refresh_drafts(conn):
        refresh_called.append(True)

    invalidated_tags = []

    async def mock_invalidate(tags, redis=None):
        invalidated_tags.extend(tags)

    monkeypatch.setattr("app.infra.auth.refresh.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.auth.refresh.refresh_auth_drafts", mock_refresh_drafts)
    monkeypatch.setattr("app.utils.cache.invalidate_tags.invalidate_tags", mock_invalidate)

    result = await refresh_auth_impl(_FakePool(), "fake-redis", profile_id=uuid4())

    assert result.success is True
    assert "auths" in result.invalidated_tags
    assert "artifacts" in result.invalidated_tags
    assert "auth_drafts_mv" in result.refreshed_views
    assert len(refresh_called) == 1


async def test_refresh_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None

    monkeypatch.setattr("app.infra.auth.refresh.resolve_profile_identity_context", mock_resolve)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await refresh_auth_impl(None, None, profile_id=uuid4())
    assert exc_info.value.status_code == 401


async def test_refresh_skips_cache_invalidation_when_redis_is_none(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return _FakeProfile(profiles_id=uuid4())

    async def mock_refresh_drafts(conn):
        pass

    monkeypatch.setattr("app.infra.auth.refresh.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.auth.refresh.refresh_auth_drafts", mock_refresh_drafts)

    result = await refresh_auth_impl(_FakePool(), None, profile_id=uuid4())
    assert result.success is True
