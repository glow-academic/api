"""Tests for department delete — monkeypatch collaborators."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.department.delete import delete_department_impl

pytestmark = pytest.mark.asyncio

_PROFILE_ID = uuid4()


@dataclass
class _FakeProfile:
    profiles_id = uuid4()
    name = "Test User"
    role = "admin"
    role_name = "Admin"
    role_description = "Administrator"
    role_artifacts = []
    primary_email = "test@test.com"
    emails = ["test@test.com"]
    primary_department_id = None
    department_ids = []
    settings_id = None
    request_limit = None
    request_limit_interval = None
    is_active = True
    session_id = None
    group_id = uuid4()
    role_level = 1
    role_permissions = []


class _FakeConn:
    async def execute(self, *a, **kw):
        pass

    async def fetch(self, *a, **kw):
        return []

    async def fetchval(self, *a, **kw):
        return None

    async def fetchrow(self, *a, **kw):
        return None

    def transaction(self):
        return self._FakeTx()

    class _FakeTx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass


class _FakePool:
    class _ctx:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, *a):
            pass

    def acquire(self):
        return self._ctx()


class TestAuth:
    async def test_raises_401_when_profile_not_found(self, monkeypatch):
        async def fake_resolve(*args, **kw):
            return None

        monkeypatch.setattr(
            "app.infra.department.delete.resolve_profile_identity_context", fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await delete_department_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, ids=[uuid4()],
            )
        assert exc_info.value.status_code == 401


class TestProfileResolved:
    async def test_profile_context_is_called(self, monkeypatch):
        called = []

        async def fake_resolve(*args, **kw):
            called.append(True)
            return _FakeProfile()

        monkeypatch.setattr(
            "app.infra.department.delete.resolve_profile_identity_context", fake_resolve,
        )

        # We expect downstream errors after profile resolution succeeds
        # but verify profile resolution was actually called
        try:
            await delete_department_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, ids=[uuid4()],
            )
        except Exception:
            pass  # downstream errors expected
        assert len(called) == 1


class TestImport:
    async def test_function_is_importable(self):
        assert callable(delete_department_impl)


@dataclass
class _SuperProfile:
    profiles_id: object = None
    role: str = "superadmin"
    name: str = "U"
    group_id: object = None
    department_ids: list = None
    role_level: int = 0
    role_permissions: list = None


async def test_delete_surfaces_failed_keycloak_idp_sync(monkeypatch):
    """A failed Keycloak de-provision sync after delete must be surfaced.

    Delete semantics differ from create/update: the DB row IS deleted, but if
    the sync fails the department's scope may still exist in Keycloak (stale —
    NOT de-provisioned). ``perform_keycloak_sync`` returns
    ``KeycloakSyncResult(success=False)`` rather than raising; before the fix
    that was dropped and the result still said "deleted successfully". Proves
    the de-provision warning reaches the caller (fails before, passes after).
    Mirrors #249, worded for delete semantics.
    """
    from app.infra.department.permissions_context import DepartmentPermissionsContext
    from app.infra.identity.keycloak_sync import KeycloakSyncResult
    from app.tools.artifacts.department.types import DeleteDepartmentsResponse

    dept_id = uuid4()

    async def mock_resolve(pool, pid, redis, **kw):
        return _SuperProfile(profiles_id=uuid4(), role_permissions=[("department", "delete")])

    async def mock_perms(conn, _id):
        return DepartmentPermissionsContext(exists=True, usage_count=0)

    async def mock_get_departments(conn, ids, **kw):
        return []  # name_map empty → "Unknown"

    async def mock_delete_departments(conn, ids, **kw):
        return DeleteDepartmentsResponse(deleted_ids=list(ids))

    async def mock_refresh(pool, redis, **kw):
        return None

    async def mock_keycloak(**kw):
        return KeycloakSyncResult(
            success=False,
            message="Keycloak sync did not complete (Keycloak unavailable)",
            error="keycloak_unavailable",
        )

    monkeypatch.setattr("app.infra.department.delete.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.department.delete.resolve_department_permissions_context", mock_perms)
    monkeypatch.setattr("app.infra.department.delete.get_departments", mock_get_departments)
    monkeypatch.setattr("app.infra.department.delete.delete_departments", mock_delete_departments)
    monkeypatch.setattr("app.infra.department.delete.refresh_department_impl", mock_refresh)
    monkeypatch.setattr(
        "app.infra.identity.keycloak_sync.perform_keycloak_sync", mock_keycloak
    )

    result = await delete_department_impl(
        _FakePool(), None, profile_id=_PROFILE_ID, ids=[dept_id],
    )

    assert len(result.results) == 1
    item = result.results[0]
    assert item.success is True
    assert item.department_id == dept_id
    # The swallowed de-provision failure must now be visible to the caller.
    assert "did not complete" in item.message.lower()
    assert "deleted successfully" in item.message  # base message preserved
