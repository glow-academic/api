"""Tests for simulation update — profile check, permission check."""

from uuid import uuid4
import pytest
from app.infra.simulation.update import update_simulation_impl
from app.infra.simulation.types import UpdateSimulationApiRequest, UpdateSimulationItem

pytestmark = pytest.mark.asyncio


async def test_update_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.simulation.update.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await update_simulation_impl(None, None, profile_id=uuid4(), request=UpdateSimulationApiRequest(simulations=[UpdateSimulationItem(id=uuid4())]))
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
    monkeypatch.setattr("app.infra.simulation.update.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await update_simulation_impl(
            None, None, profile_id=uuid4(),
            request=UpdateSimulationApiRequest(simulations=[]),
        )
    assert exc_info.value.status_code == 400


async def test_update_detail_mentions_sign_in(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.simulation.update.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await update_simulation_impl(None, None, profile_id=uuid4(), request=UpdateSimulationApiRequest(simulations=[UpdateSimulationItem(id=uuid4())]))
    assert "sign in" in exc_info.value.detail.lower()


# ============================================================================
# Cross-department reassignment guard (write-side BOLA — mirrors scenario #226)
# ============================================================================

from fastapi import HTTPException
from dataclasses import dataclass as _assign_dataclass
from uuid import uuid4 as _assign_uuid4
_PROFILE_ID = _assign_uuid4()
from app.infra.simulation.types import UpdateSimulationItem as _AssignItem


@_assign_dataclass
class _AssignDeptScopedProfile:
    """Non-top-level actor (level 1) holding simulation:update, scoped to one dept."""

    role_level = 1
    role_permissions = [("simulation", "update")]
    department_ids = None  # set per-instance

    def __init__(self, own_dept):
        self.department_ids = [own_dept]


@_assign_dataclass
class _AssignSuperadminProfile:
    """Top-level actor (level 0) — may reassign to any department."""

    role_level = 0
    role_permissions = [("simulation", "update")]
    department_ids = []


@_assign_dataclass
class _AssignPermsCtx:
    exists: bool
    department_ids: list
    cohort_usage_count: int = 0


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

    The actor can edit a simulation in their OWN department but must not be able to
    move/retag it INTO a foreign department via the body — the write-side
    cross-department BOLA. ``compute_can_edit`` only scopes the *existing* depts.
    """

    def _patch_common(self, monkeypatch, profile, ctx_dept):
        async def fake_resolve(*args, **kw):
            return profile

        async def fake_perms(*a, **kw):
            # The simulation currently lives in ``ctx_dept`` (editable for the actor).
            return _AssignPermsCtx(exists=True, department_ids=[ctx_dept])

        async def fake_values(*a, **kw):
            return []

        monkeypatch.setattr(
            "app.infra.simulation.update.resolve_profile_identity_context", fake_resolve,
        )
        monkeypatch.setattr(
            "app.infra.simulation.update.resolve_simulation_permissions_context", fake_perms,
        )
        monkeypatch.setattr(
            "app.infra.simulation.update.resolve_simulation_values", fake_values,
        )

    async def test_cross_department_reassignment_denied(self, monkeypatch):
        own_dept = uuid4()
        foreign_dept = uuid4()
        self._patch_common(monkeypatch, _AssignDeptScopedProfile(own_dept), own_dept)

        # Edit an own-dept simulation but retag it INTO a foreign dept.
        req = UpdateSimulationApiRequest(
            simulations=[_AssignItem(id=uuid4(), department_ids=[foreign_dept])]
        )
        with pytest.raises(HTTPException) as exc_info:
            await update_simulation_impl(
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
            "app.infra.simulation.update.create_denormalized_snapshot", fake_snapshot,
        )

        # Keep the simulation in the actor's own dept — guard passes, then we short-circuit
        # at the snapshot step (proving no 403 was raised).
        req = UpdateSimulationApiRequest(
            simulations=[_AssignItem(id=uuid4(), department_ids=[own_dept])]
        )
        with pytest.raises(RuntimeError, match="stop after guard"):
            await update_simulation_impl(
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
            "app.infra.simulation.update.create_denormalized_snapshot", fake_snapshot,
        )

        # Superadmin (level 0) may retag into a department they do not belong to.
        req = UpdateSimulationApiRequest(
            simulations=[_AssignItem(id=uuid4(), department_ids=[foreign_dept])]
        )
        with pytest.raises(RuntimeError, match="stop after guard"):
            await update_simulation_impl(
                _AssignPool(), object(), profile_id=_PROFILE_ID, request=req,
            )
        assert reached == [True]
