"""Tests for scenario update — monkeypatch collaborators."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.scenario.update import update_scenario_impl
from app.infra.scenario.types import UpdateScenarioApiRequest, UpdateScenarioItem

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
            "app.infra.scenario.update.resolve_profile_identity_context", fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await update_scenario_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, request=UpdateScenarioApiRequest(scenarios=[UpdateScenarioItem(id=uuid4())]),
            )
        assert exc_info.value.status_code == 401


class TestProfileResolved:
    async def test_profile_context_is_called(self, monkeypatch):
        called = []

        async def fake_resolve(*args, **kw):
            called.append(True)
            return _FakeProfile()

        monkeypatch.setattr(
            "app.infra.scenario.update.resolve_profile_identity_context", fake_resolve,
        )

        # We expect downstream errors after profile resolution succeeds
        # but verify profile resolution was actually called
        try:
            await update_scenario_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, request=UpdateScenarioApiRequest(scenarios=[UpdateScenarioItem(id=uuid4())]),
            )
        except Exception:
            pass  # downstream errors expected
        assert len(called) == 1


@dataclass
class _DeptScopedProfile:
    """Non-top-level actor (level 1) holding scenario:update, scoped to one dept."""

    role_level = 1
    role_permissions = [("scenario", "update")]
    department_ids = None  # set per-instance

    def __init__(self, own_dept):
        self.department_ids = [own_dept]


@dataclass
class _FakePermsCtx:
    exists: bool
    department_ids: list
    active_simulation_count: int = 0


class TestUpdateDepartmentAssignmentGuard:
    """Body `department_ids` on update must be a subset of the actor's own departments.

    The actor can edit a scenario in their OWN department (compute_can_edit scopes
    the scenario's *existing* depts) but must not be able to move it INTO a foreign
    department via the body — the write-side cross-department BOLA.
    """

    def _patch_common(self, monkeypatch, own_dept):
        async def fake_resolve(*args, **kw):
            return _DeptScopedProfile(own_dept)

        async def fake_perms(pool, scenario_id):
            # Scenario currently lives in the actor's own dept → editable.
            return _FakePermsCtx(exists=True, department_ids=[own_dept])

        async def fake_values(pool, redis, item, is_create):
            return []

        monkeypatch.setattr(
            "app.infra.scenario.update.resolve_profile_identity_context", fake_resolve,
        )
        monkeypatch.setattr(
            "app.infra.scenario.update.resolve_scenario_permissions_context", fake_perms,
        )
        monkeypatch.setattr(
            "app.infra.scenario.update.resolve_scenario_values", fake_values,
        )

    async def test_cross_department_reassignment_denied(self, monkeypatch):
        own_dept = uuid4()
        foreign_dept = uuid4()
        self._patch_common(monkeypatch, own_dept)

        # Edit an own-dept scenario but retag it INTO a foreign dept.
        req = UpdateScenarioApiRequest(
            scenarios=[UpdateScenarioItem(id=uuid4(), department_ids=[foreign_dept])]
        )
        with pytest.raises(HTTPException) as exc_info:
            await update_scenario_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, request=req,
            )
        assert exc_info.value.status_code == 403

    async def test_own_department_reassignment_passes_guard(self, monkeypatch):
        own_dept = uuid4()
        reached = []
        self._patch_common(monkeypatch, own_dept)

        async def fake_snapshot(*a, **kw):
            reached.append(True)
            raise RuntimeError("stop after guard")

        monkeypatch.setattr(
            "app.infra.scenario.update.create_denormalized_snapshot", fake_snapshot,
        )

        # Legit: keep the scenario in the actor's own dept — guard passes, then
        # we short-circuit at the snapshot step (proving no 403 was raised).
        req = UpdateScenarioApiRequest(
            scenarios=[UpdateScenarioItem(id=uuid4(), department_ids=[own_dept])]
        )
        with pytest.raises(RuntimeError, match="stop after guard"):
            await update_scenario_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, request=req,
            )
        assert reached == [True]


class TestImport:
    async def test_function_is_importable(self):
        assert callable(update_scenario_impl)
