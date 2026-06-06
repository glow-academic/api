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


class _TxD:
    async def __aenter__(self):
        return None
    async def __aexit__(self, *a):
        pass


class _ConnD:
    def transaction(self):
        return _TxD()


class _CtxD:
    async def __aenter__(self):
        return _ConnD()
    async def __aexit__(self, *a):
        pass


class _PoolD:
    def acquire(self):
        return _CtxD()


async def test_delete_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.auth.delete.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await delete_auth_impl(_Pool(), None, profile_id=uuid4(), ids=[uuid4()])
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
        await delete_auth_impl(_Pool(), None, profile_id=uuid4(), ids=[uuid4()])
    assert exc_info.value.status_code == 404


async def test_delete_detail_mentions_sign_in(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.auth.delete.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await delete_auth_impl(_Pool(), None, profile_id=uuid4(), ids=[uuid4()])
    assert "sign in" in exc_info.value.detail.lower()


async def test_delete_surfaces_failed_keycloak_idp_sync(monkeypatch):
    """A failed Keycloak de-provision sync after delete must be surfaced.

    Delete semantics differ from create/update: the DB row IS deleted, but if
    the sync fails the provider may still exist in Keycloak (stale IdP — NOT
    de-provisioned). ``perform_keycloak_sync`` returns
    ``KeycloakSyncResult(success=False)`` rather than raising; before the fix
    that was dropped and the result still said "deleted successfully". Proves
    the de-provision warning now reaches the caller (fails before, passes
    after). Mirrors #249, worded for delete semantics.
    """
    from app.infra.auth.permissions_context import AuthPermissionsContext
    from app.infra.identity.keycloak_sync import KeycloakSyncResult
    from app.tools.artifacts.auth.types import DeleteAuthsResponse

    auth_id = uuid4()

    async def mock_resolve(pool, pid, redis, **kw):
        return _P(profiles_id=uuid4(), role_permissions=[("auth", "delete")])

    async def mock_perms(conn, _id):
        return AuthPermissionsContext(exists=True, department_ids=[], active_settings_count=0)

    async def mock_get_auths(conn, ids, **kw):
        return []  # name_map empty → "Unknown"

    async def mock_delete_auths(conn, ids, **kw):
        return DeleteAuthsResponse(deleted_ids=list(ids))

    async def mock_refresh(pool, redis, **kw):
        return None

    async def mock_keycloak(**kw):
        return KeycloakSyncResult(
            success=False,
            message="Keycloak sync did not complete (Keycloak unavailable)",
            error="keycloak_unavailable",
        )

    monkeypatch.setattr("app.infra.auth.delete.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.auth.delete.resolve_auth_permissions_context", mock_perms)
    monkeypatch.setattr("app.infra.auth.delete.get_auths", mock_get_auths)
    monkeypatch.setattr("app.infra.auth.delete.delete_auths", mock_delete_auths)
    monkeypatch.setattr("app.infra.auth.delete.refresh_auth_impl", mock_refresh)
    monkeypatch.setattr(
        "app.infra.identity.keycloak_sync.perform_keycloak_sync", mock_keycloak
    )

    result = await delete_auth_impl(_PoolD(), None, profile_id=uuid4(), ids=[auth_id])

    assert len(result.results) == 1
    item = result.results[0]
    assert item.success is True
    # The swallowed de-provision failure must now be visible to the caller.
    assert "did not complete" in item.message.lower()
    assert "deleted successfully" in item.message  # base message preserved
    assert item.message != f"Auth 'Unknown' deleted successfully"
