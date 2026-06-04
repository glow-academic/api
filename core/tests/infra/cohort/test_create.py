"""Tests for cohort create — monkeypatch collaborators."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.cohort.create import create_cohort_impl
from app.infra.cohort.types import CreateCohortApiRequest

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
            "app.infra.cohort.create.resolve_profile_identity_context", fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_cohort_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID,
                request=CreateCohortApiRequest(cohorts=[]),
            )
        assert exc_info.value.status_code == 401


class TestProfileResolved:
    async def test_profile_context_is_called(self, monkeypatch):
        called = []

        async def fake_resolve(*args, **kw):
            called.append(True)
            return _FakeProfile()

        monkeypatch.setattr(
            "app.infra.cohort.create.resolve_profile_identity_context", fake_resolve,
        )

        # We expect downstream errors after profile resolution succeeds
        # but verify profile resolution was actually called
        try:
            await create_cohort_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID,
                request=CreateCohortApiRequest(cohorts=[]),
            )
        except Exception:
            pass  # downstream errors expected
        assert len(called) == 1


class TestImport:
    async def test_function_is_importable(self):
        assert callable(create_cohort_impl)


# ============================================================================
# Cross-department assignment guard (write-side BOLA — mirrors scenario #226)
# ============================================================================

from dataclasses import dataclass as _assign_dataclass
from app.infra.cohort.types import CreateCohortItem as _AssignItem


@_assign_dataclass
class _AssignDeptScopedProfile:
    """Non-top-level actor (level 1) holding cohort:create, scoped to one dept."""

    role_level = 1
    role_permissions = [("cohort", "create")]
    department_ids = None  # set per-instance

    def __init__(self, own_dept):
        self.department_ids = [own_dept]


@_assign_dataclass
class _AssignSuperadminProfile:
    """Top-level actor (level 0) — may assign any department."""

    role_level = 0
    role_permissions = [("cohort", "create")]
    department_ids = []


class _AssignConn:
    async def execute(self, *a, **kw):
        pass

    async def fetch(self, *a, **kw):
        return []

    async def fetchval(self, *a, **kw):
        return None

    async def fetchrow(self, *a, **kw):
        return None

    def transaction(self):
        return self._Tx()

    class _Tx:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass


class _AssignPool:
    class _ctx:
        async def __aenter__(self):
            return _AssignConn()

        async def __aexit__(self, *a):
            pass

    def acquire(self):
        return self._ctx()


class TestCreateDepartmentAssignmentGuard:
    """Body ``department_ids`` must be a subset of the actor's own departments."""

    def _patch_common(self, monkeypatch, profile):
        async def fake_resolve(*args, **kw):
            return profile

        async def fake_values(*a, **kw):
            return []  # no validation errors; leaves item.department_ids untouched

        monkeypatch.setattr(
            "app.infra.cohort.create.resolve_profile_identity_context", fake_resolve,
        )
        monkeypatch.setattr(
            "app.infra.cohort.create.resolve_cohort_values", fake_values,
        )

    async def test_cross_department_create_denied(self, monkeypatch):
        own_dept = uuid4()
        foreign_dept = uuid4()
        self._patch_common(monkeypatch, _AssignDeptScopedProfile(own_dept))

        req = CreateCohortApiRequest(
            cohorts=[_AssignItem(department_ids=[foreign_dept])]
        )
        with pytest.raises(HTTPException) as exc_info:
            await create_cohort_impl(
                _AssignPool(), object(), profile_id=_PROFILE_ID, request=req,
            )
        assert exc_info.value.status_code == 403

    async def test_own_department_create_passes_guard(self, monkeypatch):
        own_dept = uuid4()
        reached = []
        self._patch_common(monkeypatch, _AssignDeptScopedProfile(own_dept))

        async def fake_snapshot(*a, **kw):
            reached.append(True)
            raise RuntimeError("stop after guard")

        monkeypatch.setattr(
            "app.infra.cohort.create.create_denormalized_snapshot", fake_snapshot,
        )

        req = CreateCohortApiRequest(
            cohorts=[_AssignItem(department_ids=[own_dept])]
        )
        with pytest.raises(RuntimeError, match="stop after guard"):
            await create_cohort_impl(
                _AssignPool(), object(), profile_id=_PROFILE_ID, request=req,
            )
        assert reached == [True]

    async def test_superadmin_assigns_any_department(self, monkeypatch):
        foreign_dept = uuid4()
        reached = []
        self._patch_common(monkeypatch, _AssignSuperadminProfile())

        async def fake_snapshot(*a, **kw):
            reached.append(True)
            raise RuntimeError("stop after guard")

        monkeypatch.setattr(
            "app.infra.cohort.create.create_denormalized_snapshot", fake_snapshot,
        )

        # Superadmin (level 0) may assign a department they do not "belong" to.
        req = CreateCohortApiRequest(
            cohorts=[_AssignItem(department_ids=[foreign_dept])]
        )
        with pytest.raises(RuntimeError, match="stop after guard"):
            await create_cohort_impl(
                _AssignPool(), object(), profile_id=_PROFILE_ID, request=req,
            )
        assert reached == [True]
