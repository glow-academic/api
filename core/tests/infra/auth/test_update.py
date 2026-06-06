"""Tests for auth update — profile check, permission check."""

from dataclasses import dataclass
from uuid import uuid4
import pytest
from app.infra.auth.update import update_auth_impl
from app.infra.auth.types import UpdateAuthApiRequest, UpdateAuthItem

pytestmark = pytest.mark.asyncio


@dataclass
class _FakeProfileU:
    profiles_id: object = None
    role: str = "superadmin"
    name: str = "U"
    group_id: object = None
    department_ids: list = None
    role_level: int = 0
    role_permissions: list = None


class _FakeTxU:
    async def __aenter__(self):
        return None
    async def __aexit__(self, *a):
        pass


class _FakeConnU:
    def transaction(self):
        return _FakeTxU()


class _FakePoolConnU:
    async def __aenter__(self):
        return _FakeConnU()
    async def __aexit__(self, *a):
        pass


class _FakePoolU:
    def acquire(self):
        return _FakePoolConnU()


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


async def test_update_surfaces_failed_keycloak_idp_sync(monkeypatch):
    """A failed Keycloak IdP re-sync after update must NOT report unqualified success.

    ``perform_keycloak_sync`` returns ``KeycloakSyncResult(success=False)`` on
    failure rather than raising. Before the fix that ``False`` was dropped (the
    ``except Exception`` was dead code) and every result still said "Auth
    updated successfully", even though the IdP config in Keycloak is now stale.
    This proves the warning reaches the caller (fails before, passes after).
    Mirrors #249's create fix.
    """
    from app.infra.auth.permissions_context import AuthPermissionsContext
    from app.infra.identity.keycloak_sync import KeycloakSyncResult
    from app.tools.artifacts.auth.types import UpdateAuthResponse

    auth_id = uuid4()

    async def mock_resolve(pool, pid, redis, **kw):
        return _FakeProfileU(profiles_id=uuid4(), role_permissions=[("auth", "update")])

    async def mock_perms(conn, _id):
        return AuthPermissionsContext(exists=True, department_ids=[], active_settings_count=0)

    async def mock_resolve_values(conn, redis, item, **kw):
        return []  # no validation errors

    async def mock_get_artifacts(conn, ids, **kw):
        return []

    async def mock_snapshot(pool, redis, **kw):
        return uuid4()

    async def mock_update_artifact(conn, _id, **kw):
        return UpdateAuthResponse(id=auth_id)

    async def mock_refresh(pool, redis, **kw):
        return None

    async def mock_hydrate(pool, redis, **kw):
        return []

    async def mock_keycloak(**kw):
        return KeycloakSyncResult(
            success=False,
            message="Keycloak sync did not complete (Keycloak unavailable)",
            error="keycloak_unavailable",
        )

    monkeypatch.setattr("app.infra.auth.update.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.auth.update.resolve_auth_permissions_context", mock_perms)
    monkeypatch.setattr("app.infra.auth.update.resolve_auth_values", mock_resolve_values)
    monkeypatch.setattr("app.infra.auth.update.get_auth_artifacts", mock_get_artifacts)
    monkeypatch.setattr("app.infra.auth.update.create_denormalized_snapshot", mock_snapshot)
    monkeypatch.setattr("app.infra.auth.update.update_auth_artifact", mock_update_artifact)
    monkeypatch.setattr("app.infra.auth.update.refresh_auth_impl", mock_refresh)
    monkeypatch.setattr("app.infra.auth.hydrate_list_rows.hydrate_auth_list_rows", mock_hydrate)
    monkeypatch.setattr(
        "app.infra.identity.keycloak_sync.perform_keycloak_sync", mock_keycloak
    )

    result = await update_auth_impl(
        _FakePoolU(), None, profile_id=uuid4(),
        request=UpdateAuthApiRequest(auths=[UpdateAuthItem(id=auth_id)]),
    )

    assert len(result.results) == 1
    item = result.results[0]
    assert item.success is True
    # The swallowed sync failure must now be visible to the caller.
    assert "did not complete" in item.message.lower()
    assert item.message != "Auth updated successfully"
