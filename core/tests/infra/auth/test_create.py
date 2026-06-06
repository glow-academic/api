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


async def test_create_surfaces_failed_keycloak_idp_sync(monkeypatch):
    """A failed Keycloak IdP sync must NOT report an unqualified success.

    ``perform_keycloak_sync`` does not raise on failure — it returns
    ``KeycloakSyncResult(success=False)``. Before the fix that ``False`` was
    dropped and every result still said "Auth created successfully", even
    though no one can log in through the just-created provider until Keycloak
    re-syncs. This proves the warning now reaches the caller (fails before the
    fix, passes after). Mirrors #247's surfaced-error contract.
    """
    from app.infra.identity.keycloak_sync import KeycloakSyncResult
    from app.tools.artifacts.auth.types import CreateAuthResponse

    new_auth_id = uuid4()

    async def mock_resolve(pool, pid, redis, **kw):
        return _FakeProfile(
            profiles_id=uuid4(),
            role="superadmin",
            role_level=0,
            role_permissions=[
                ("auth", "create"), ("auth", "update"), ("auth", "delete"),
                ("auth", "duplicate"), ("auth", "draft"),
            ],
        )

    async def mock_resolve_values(conn, redis, item, **kw):
        return []  # no validation errors

    async def mock_snapshot(pool, redis, **kw):
        return uuid4()

    async def mock_create_artifact(conn, **kw):
        return CreateAuthResponse(id=new_auth_id)

    async def mock_refresh(pool, redis, **kw):
        return None

    async def mock_hydrate(pool, redis, **kw):
        return []

    # Keycloak unreachable: sync reports success=False rather than raising.
    async def mock_keycloak(**kw):
        return KeycloakSyncResult(
            success=False,
            message="Keycloak sync did not complete (Keycloak unavailable)",
            error="keycloak_unavailable",
        )

    monkeypatch.setattr(
        "app.infra.auth.create.resolve_profile_identity_context", mock_resolve
    )
    monkeypatch.setattr(
        "app.infra.auth.create.resolve_auth_values", mock_resolve_values
    )
    monkeypatch.setattr(
        "app.infra.auth.create.create_denormalized_snapshot", mock_snapshot
    )
    monkeypatch.setattr(
        "app.infra.auth.create.create_auth_artifact", mock_create_artifact
    )
    monkeypatch.setattr("app.infra.auth.create.refresh_auth_impl", mock_refresh)
    # hydrate_auth_list_rows is imported lazily inside create_auth_impl — patch
    # at its source module.
    monkeypatch.setattr(
        "app.infra.auth.hydrate_list_rows.hydrate_auth_list_rows", mock_hydrate
    )
    monkeypatch.setattr(
        "app.infra.identity.keycloak_sync.perform_keycloak_sync", mock_keycloak
    )

    request = CreateAuthApiRequest(auths=[{"name": "Acme SSO"}])
    result = await create_auth_impl(
        _FakePool(), None, profile_id=uuid4(), request=request
    )

    assert len(result.results) == 1
    item = result.results[0]
    assert item.success is True
    assert item.auth_id == new_auth_id
    # The swallowed sync failure must now be visible to the caller.
    assert "did not complete" in item.message.lower()
    assert item.message != "Auth created successfully"
