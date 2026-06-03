"""Tests for field refresh — monkeypatch collaborators."""

from dataclasses import dataclass
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.field.refresh import refresh_field_impl

pytestmark = pytest.mark.asyncio

_PROFILE_ID = uuid4()


@dataclass
class _FakeProfile:
    profiles_id = uuid4()
    name = "Test"
    role = "admin"
    department_ids = []
    group_id = uuid4()
    session_id = None
    role_level = 1
    role_permissions = []


class _FakeConn:
    pass


class _FakePool:
    class _ctx:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, *a):
            pass

    def acquire(self):
        return self._ctx()


class TestRefreshSuccess:
    async def test_returns_success_with_views_and_tags(self, monkeypatch):
        invalidated = []

        async def fake_resolve(pool, pid, redis, **kw):
            return _FakeProfile()

        async def fake_invalidate(tags, *, redis):
            invalidated.extend(tags)

        monkeypatch.setattr(
            "app.infra.refresh.queue.resolve_profile_identity_context",
            fake_resolve,
        )
        monkeypatch.setattr(
            "app.utils.cache.invalidate_tags.invalidate_tags",
            fake_invalidate,
        )

        result = await refresh_field_impl(_FakePool(), AsyncMock(), profile_id=_PROFILE_ID)

        assert result.success is True
        assert "field_drafts_mv" in result.refreshed_views
        assert result.invalidated_tags == ["fields", "artifacts"]


class TestRefreshAuth:
    async def test_raises_401_when_profile_not_found(self, monkeypatch):
        async def fake_resolve(pool, pid, redis, **kw):
            return None

        monkeypatch.setattr(
            "app.infra.refresh.queue.resolve_profile_identity_context",
            fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await refresh_field_impl(object(), object(), profile_id=_PROFILE_ID)
        assert exc_info.value.status_code == 401


class TestRefreshRedisNone:
    async def test_skips_invalidation_when_redis_is_none(self, monkeypatch):
        async def fake_resolve(pool, pid, redis, **kw):
            return _FakeProfile()

        monkeypatch.setattr(
            "app.infra.refresh.queue.resolve_profile_identity_context",
            fake_resolve,
        )

        result = await refresh_field_impl(_FakePool(), None, profile_id=_PROFILE_ID)
        assert result.success is True
