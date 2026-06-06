"""Tests for department update — monkeypatch collaborators."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.department.update import update_department_impl
from app.infra.department.types import UpdateDepartmentApiRequest, UpdateDepartmentItem

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
            "app.infra.department.update.resolve_profile_identity_context", fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await update_department_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, request=UpdateDepartmentApiRequest(departments=[UpdateDepartmentItem(id=uuid4())]),
            )
        assert exc_info.value.status_code == 401


class TestProfileResolved:
    async def test_profile_context_is_called(self, monkeypatch):
        called = []

        async def fake_resolve(*args, **kw):
            called.append(True)
            return _FakeProfile()

        monkeypatch.setattr(
            "app.infra.department.update.resolve_profile_identity_context", fake_resolve,
        )

        # We expect downstream errors after profile resolution succeeds
        # but verify profile resolution was actually called
        try:
            await update_department_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, request=UpdateDepartmentApiRequest(departments=[UpdateDepartmentItem(id=uuid4())]),
            )
        except Exception:
            pass  # downstream errors expected
        assert len(called) == 1


class TestImport:
    async def test_function_is_importable(self):
        assert callable(update_department_impl)


@dataclass
class _SuperProfile:
    profiles_id: object = None
    role: str = "superadmin"
    name: str = "U"
    group_id: object = None
    department_ids: list = None
    role_level: int = 0
    role_permissions: list = None


async def test_update_surfaces_failed_keycloak_idp_sync(monkeypatch):
    """A failed per-department Keycloak re-sync must NOT report unqualified success.

    ``perform_keycloak_sync`` returns ``KeycloakSyncResult(success=False)`` on
    failure rather than raising. Before the fix that ``False`` was dropped (the
    ``except Exception`` was dead code) and every result still said "Department
    updated successfully", even though Keycloak now holds stale config. Proves
    the warning reaches the caller (fails before, passes after). Mirrors #249.
    """
    from app.infra.department.permissions_context import DepartmentPermissionsContext
    from app.infra.identity.keycloak_sync import KeycloakSyncResult
    from app.tools.artifacts.department.types import UpdateDepartmentResponse

    dept_id = uuid4()

    async def mock_resolve(pool, pid, redis, **kw):
        return _SuperProfile(profiles_id=uuid4(), role_permissions=[("department", "update")])

    async def mock_perms(conn, _id):
        return DepartmentPermissionsContext(exists=True, usage_count=0)

    async def mock_resolve_values(conn, redis, item, **kw):
        return []  # no validation errors

    async def mock_get_artifacts(conn, ids, **kw):
        return []

    async def mock_snapshot(pool, redis, **kw):
        return uuid4()

    async def mock_update_artifact(conn, _id, **kw):
        return UpdateDepartmentResponse(id=dept_id)

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

    monkeypatch.setattr("app.infra.department.update.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.department.update.resolve_department_permissions_context", mock_perms)
    monkeypatch.setattr("app.infra.department.update.resolve_department_values", mock_resolve_values)
    monkeypatch.setattr("app.infra.department.update.get_department_artifacts", mock_get_artifacts)
    monkeypatch.setattr("app.infra.department.update.create_denormalized_snapshot", mock_snapshot)
    monkeypatch.setattr("app.infra.department.update.update_department_artifact", mock_update_artifact)
    monkeypatch.setattr("app.infra.department.update.refresh_department_impl", mock_refresh)
    monkeypatch.setattr(
        "app.infra.department.hydrate_list_rows.hydrate_department_list_rows", mock_hydrate
    )
    monkeypatch.setattr(
        "app.infra.identity.keycloak_sync.perform_keycloak_sync", mock_keycloak
    )

    result = await update_department_impl(
        _FakePool(), None, profile_id=_PROFILE_ID,
        request=UpdateDepartmentApiRequest(departments=[UpdateDepartmentItem(id=dept_id)]),
    )

    assert len(result.results) == 1
    item = result.results[0]
    assert item.success is True
    assert item.department_id == dept_id
    # The swallowed sync failure must now be visible to the caller.
    assert "did not complete" in item.message.lower()
    assert item.message != "Department updated successfully"
