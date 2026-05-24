"""Tests for auth create — profile check, permission check, orchestration."""

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.infra.auth.create import create_auth_impl

pytestmark = pytest.mark.asyncio(loop_scope="session")


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
        await create_auth_impl(_FakePool(), None, profile_id=uuid4(), items=[])
    assert exc_info.value.status_code == 401


async def test_create_raises_403_for_non_superadmin(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return _FakeProfile(profiles_id=uuid4(), role="member", role_level=3, role_permissions=[])

    monkeypatch.setattr(
        "app.infra.auth.create.resolve_profile_identity_context", mock_resolve
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await create_auth_impl(_FakePool(), None, profile_id=uuid4(), items=[])
    assert exc_info.value.status_code == 403


async def test_create_returns_results_for_empty_items(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return _FakeProfile(profiles_id=uuid4(), role="superadmin", role_level=0, role_permissions=[("auth", "create"), ("auth", "update"), ("auth", "delete"), ("auth", "duplicate"), ("auth", "draft")])

    async def mock_invalidate(tags, redis=None):
        pass

    async def mock_keycloak(**kw):
        pass

    monkeypatch.setattr(
        "app.infra.auth.create.resolve_profile_identity_context", mock_resolve
    )
    monkeypatch.setattr("app.infra.auth.create.invalidate_tags", mock_invalidate)
    monkeypatch.setattr("app.infra.auth.create.perform_keycloak_sync", mock_keycloak)

    result = await create_auth_impl(_FakePool(), None, profile_id=uuid4(), items=[])
    assert hasattr(result, "results")
    assert len(result.results) == 0
