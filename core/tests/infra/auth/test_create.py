"""Tests for auth create — profile check, permission check, orchestration."""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.infra.auth.create import create_auth_impl
from app.infra.auth.types import CreateAuthApiRequest

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


class _FakeTx:
    async def __aenter__(self):
        return None
    async def __aexit__(self, *a):
        pass


class _FakeConn:
    def transaction(self):
        return _FakeTx()


class _FakePoolConn:
    async def __aenter__(self):
        return _FakeConn()
    async def __aexit__(self, *a):
        pass


class _FakePool:
    def acquire(self):
        return _FakePoolConn()


async def test_create_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None

    monkeypatch.setattr(
        "app.infra.auth.create.resolve_profile_identity_context", mock_resolve
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await create_auth_impl(_FakePool(), None, profile_id=uuid4(), request=CreateAuthApiRequest(auths=[]))
    assert exc_info.value.status_code == 401


async def test_create_raises_403_for_non_superadmin(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return _FakeProfile(profiles_id=uuid4(), role="member", role_level=3, role_permissions=[])

    monkeypatch.setattr(
        "app.infra.auth.create.resolve_profile_identity_context", mock_resolve
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await create_auth_impl(_FakePool(), None, profile_id=uuid4(), request=CreateAuthApiRequest(auths=[]))
    assert exc_info.value.status_code == 403


async def test_create_returns_results_for_empty_items(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return _FakeProfile(profiles_id=uuid4(), role="superadmin", role_level=0, role_permissions=[("auth", "create"), ("auth", "update"), ("auth", "delete"), ("auth", "duplicate"), ("auth", "draft")])

    async def mock_keycloak(**kw):
        pass

    monkeypatch.setattr(
        "app.infra.auth.create.resolve_profile_identity_context", mock_resolve
    )
    # The empty-items path still calls refresh_auth_impl, which delegates to
    # enqueue_refreshes → its own permission check via the queue module's
    # resolve_profile_identity_context. Patch that too so the inner refresh
    # passes (cache invalidation now lives in enqueue_refreshes, not here).
    monkeypatch.setattr(
        "app.infra.refresh.queue.resolve_profile_identity_context", mock_resolve
    )
    # perform_keycloak_sync is imported lazily inside create_auth_impl, so it is
    # not a module attribute of app.infra.auth.create — patch it at its source.
    monkeypatch.setattr(
        "app.infra.identity.keycloak_sync.perform_keycloak_sync", mock_keycloak
    )

    result = await create_auth_impl(_FakePool(), None, profile_id=uuid4(), request=CreateAuthApiRequest(auths=[]))
    assert hasattr(result, "results")
    assert len(result.results) == 0
