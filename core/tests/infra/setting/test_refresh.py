"""Tests for setting refresh — monkeypatch collaborators."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.setting.refresh import refresh_setting_impl

pytestmark = pytest.mark.asyncio(loop_scope="session")

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

        async def fake_refresh(conn):
            pass

        async def fake_invalidate(tags, *, redis):
            invalidated.extend(tags)

        monkeypatch.setattr(
            "app.infra.setting.refresh.resolve_profile_identity_context",
            fake_resolve,
        )
        monkeypatch.setattr(
            "app.infra.setting.refresh.refresh_setting_drafts",
            fake_refresh,
        )
        monkeypatch.setattr(
            "app.utils.cache.invalidate_tags.invalidate_tags",
            fake_invalidate,
        )

        result = await refresh_setting_impl(_FakePool(), object(), profile_id=_PROFILE_ID)

        assert result.success is True
        assert result.refreshed_views == ["setting_drafts_mv"]
        assert result.invalidated_tags == ["settings", "artifacts"]


class TestRefreshAuth:
    async def test_raises_401_when_profile_not_found(self, monkeypatch):
        async def fake_resolve(pool, pid, redis, **kw):
            return None

        monkeypatch.setattr(
            "app.infra.setting.refresh.resolve_profile_identity_context",
            fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await refresh_setting_impl(object(), object(), profile_id=_PROFILE_ID)
        assert exc_info.value.status_code == 401


class TestRefreshRedisNone:
    async def test_skips_invalidation_when_redis_is_none(self, monkeypatch):
        async def fake_resolve(pool, pid, redis, **kw):
            return _FakeProfile()

        async def fake_refresh(conn):
            pass

        monkeypatch.setattr(
            "app.infra.setting.refresh.resolve_profile_identity_context",
            fake_resolve,
        )
        monkeypatch.setattr(
            "app.infra.setting.refresh.refresh_setting_drafts",
            fake_refresh,
        )

        result = await refresh_setting_impl(_FakePool(), None, profile_id=_PROFILE_ID)
        assert result.success is True
