"""Tests for department create — monkeypatch collaborators."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.department.create import create_department_impl
from app.infra.department.types import CreateDepartmentApiRequest

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
            "app.infra.department.create.resolve_profile_identity_context", fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_department_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID,
                request=CreateDepartmentApiRequest(departments=[]),
            )
        assert exc_info.value.status_code == 401


class TestProfileResolved:
    async def test_profile_context_is_called(self, monkeypatch):
        called = []

        async def fake_resolve(*args, **kw):
            called.append(True)
            return _FakeProfile()

        monkeypatch.setattr(
            "app.infra.department.create.resolve_profile_identity_context", fake_resolve,
        )

        # We expect downstream errors after profile resolution succeeds
        # but verify profile resolution was actually called
        try:
            await create_department_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID,
                request=CreateDepartmentApiRequest(departments=[]),
            )
        except Exception:
            pass  # downstream errors expected
        assert len(called) == 1


class TestImport:
    async def test_function_is_importable(self):
        assert callable(create_department_impl)


@dataclass
class _SuperProfile:
    profiles_id: object = None
    role: str = "superadmin"
    name: str = "U"
    group_id: object = None
    department_ids: list = None
    role_level: int = 0
    role_permissions: list = None


async def test_create_surfaces_failed_keycloak_idp_sync(monkeypatch):
    """A failed per-department Keycloak sync must NOT report unqualified success.

    ``perform_keycloak_sync`` returns ``KeycloakSyncResult(success=False)`` on
    failure rather than raising. Before the fix that ``False`` was dropped (the
    ``except Exception`` was dead code) and every result still said "Department
    created successfully", even though the department isn't reflected in
    Keycloak. Proves the warning now reaches the caller (fails before, passes
    after). Mirrors #249's auth-create fix.
    """
    from app.infra.identity.keycloak_sync import KeycloakSyncResult
    from app.tools.artifacts.department.types import CreateDepartmentResponse

    dept_id = uuid4()

    async def mock_resolve(pool, pid, redis, **kw):
        return _SuperProfile(profiles_id=uuid4(), role_permissions=[("department", "create")])

    async def mock_resolve_values(conn, redis, item, **kw):
        return []  # no validation errors

    async def mock_snapshot(pool, redis, **kw):
        return uuid4()

    async def mock_create_artifact(conn, **kw):
        return CreateDepartmentResponse(id=dept_id)

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

    monkeypatch.setattr("app.infra.department.create.resolve_profile_identity_context", mock_resolve)
    monkeypatch.setattr("app.infra.department.create.resolve_department_values", mock_resolve_values)
    monkeypatch.setattr("app.infra.department.create.create_denormalized_snapshot", mock_snapshot)
    monkeypatch.setattr("app.infra.department.create.create_department_artifact", mock_create_artifact)
    monkeypatch.setattr("app.infra.department.create.refresh_department_impl", mock_refresh)
    monkeypatch.setattr(
        "app.infra.department.hydrate_list_rows.hydrate_department_list_rows", mock_hydrate
    )
    monkeypatch.setattr(
        "app.infra.identity.keycloak_sync.perform_keycloak_sync", mock_keycloak
    )

    result = await create_department_impl(
        _FakePool(), None, profile_id=_PROFILE_ID,
        request=CreateDepartmentApiRequest(departments=[{"name": "Physics"}]),
    )

    assert len(result.results) == 1
    item = result.results[0]
    assert item.success is True
    assert item.department_id == dept_id
    # The swallowed sync failure must now be visible to the caller.
    assert "did not complete" in item.message.lower()
    assert item.message != "Department created successfully"
