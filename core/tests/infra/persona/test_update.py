"""Tests for persona update — monkeypatch collaborators."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.persona.update import update_persona_impl
from app.infra.persona.types import UpdatePersonaApiRequest, UpdatePersonaItem

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
            "app.infra.persona.update.resolve_profile_identity_context", fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await update_persona_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID,
                request=UpdatePersonaApiRequest(personas=[UpdatePersonaItem(id=uuid4())]),
            )
        assert exc_info.value.status_code == 401


class TestProfileResolved:
    async def test_profile_context_is_called(self, monkeypatch):
        called = []

        async def fake_resolve(*args, **kw):
            called.append(True)
            return _FakeProfile()

        monkeypatch.setattr(
            "app.infra.persona.update.resolve_profile_identity_context", fake_resolve,
        )

        # We expect downstream errors after profile resolution succeeds
        # but verify profile resolution was actually called
        try:
            await update_persona_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID,
                request=UpdatePersonaApiRequest(personas=[UpdatePersonaItem(id=uuid4())]),
            )
        except Exception:
            pass  # downstream errors expected
        assert len(called) == 1


class TestImport:
    async def test_function_is_importable(self):
        assert callable(update_persona_impl)


# ============================================================================
# Cross-department reassignment guard (write-side BOLA — mirrors scenario #226)
# ============================================================================

from dataclasses import dataclass as _assign_dataclass
from app.infra.persona.types import UpdatePersonaItem as _AssignItem


@_assign_dataclass
class _AssignDeptScopedProfile:
    """Non-top-level actor (level 1) holding persona:update, scoped to one dept."""

    role_level = 1
    role_permissions = [("persona", "update")]
    department_ids = None  # set per-instance

    def __init__(self, own_dept):
        self.department_ids = [own_dept]


@_assign_dataclass
class _AssignSuperadminProfile:
    """Top-level actor (level 0) — may reassign to any department."""

    role_level = 0
    role_permissions = [("persona", "update")]
    department_ids = []


@_assign_dataclass
class _AssignPermsCtx:
    exists: bool
    department_ids: list
    active_scenario_count: int = 0


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


class TestUpdateDepartmentAssignmentGuard:
    """Body ``department_ids`` on update must be a subset of the actor's own departments.

    The actor can edit a persona in their OWN department but must not be able to
    move/retag it INTO a foreign department via the body — the write-side
    cross-department BOLA. ``compute_can_edit`` only scopes the *existing* depts.
    """

    def _patch_common(self, monkeypatch, profile, ctx_dept):
        async def fake_resolve(*args, **kw):
            return profile

        async def fake_perms(*a, **kw):
            # The persona currently lives in ``ctx_dept`` (editable for the actor).
            return _AssignPermsCtx(exists=True, department_ids=[ctx_dept])

        async def fake_values(*a, **kw):
            return []

        monkeypatch.setattr(
            "app.infra.persona.update.resolve_profile_identity_context", fake_resolve,
        )
        monkeypatch.setattr(
            "app.infra.persona.update.resolve_persona_permissions_context", fake_perms,
        )
        monkeypatch.setattr(
            "app.infra.persona.update.resolve_persona_values", fake_values,
        )

    async def test_cross_department_reassignment_denied(self, monkeypatch):
        own_dept = uuid4()
        foreign_dept = uuid4()
        self._patch_common(monkeypatch, _AssignDeptScopedProfile(own_dept), own_dept)

        # Edit an own-dept persona but retag it INTO a foreign dept.
        req = UpdatePersonaApiRequest(
            personas=[_AssignItem(id=uuid4(), department_ids=[foreign_dept])]
        )
        with pytest.raises(HTTPException) as exc_info:
            await update_persona_impl(
                _AssignPool(), object(), profile_id=_PROFILE_ID, request=req,
            )
        assert exc_info.value.status_code == 403

    async def test_own_department_reassignment_passes_guard(self, monkeypatch):
        own_dept = uuid4()
        reached = []
        self._patch_common(monkeypatch, _AssignDeptScopedProfile(own_dept), own_dept)

        async def fake_snapshot(*a, **kw):
            reached.append(True)
            raise RuntimeError("stop after guard")

        monkeypatch.setattr(
            "app.infra.persona.update.create_denormalized_snapshot", fake_snapshot,
        )

        # Keep the persona in the actor's own dept — guard passes, then we short-circuit
        # at the snapshot step (proving no 403 was raised).
        req = UpdatePersonaApiRequest(
            personas=[_AssignItem(id=uuid4(), department_ids=[own_dept])]
        )
        with pytest.raises(RuntimeError, match="stop after guard"):
            await update_persona_impl(
                _AssignPool(), object(), profile_id=_PROFILE_ID, request=req,
            )
        assert reached == [True]

    async def test_superadmin_reassigns_any_department(self, monkeypatch):
        existing_dept = uuid4()
        foreign_dept = uuid4()
        reached = []
        self._patch_common(monkeypatch, _AssignSuperadminProfile(), existing_dept)

        async def fake_snapshot(*a, **kw):
            reached.append(True)
            raise RuntimeError("stop after guard")

        monkeypatch.setattr(
            "app.infra.persona.update.create_denormalized_snapshot", fake_snapshot,
        )

        # Superadmin (level 0) may retag into a department they do not belong to.
        req = UpdatePersonaApiRequest(
            personas=[_AssignItem(id=uuid4(), department_ids=[foreign_dept])]
        )
        with pytest.raises(RuntimeError, match="stop after guard"):
            await update_persona_impl(
                _AssignPool(), object(), profile_id=_PROFILE_ID, request=req,
            )
        assert reached == [True]
