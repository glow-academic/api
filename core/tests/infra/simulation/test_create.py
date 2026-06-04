"""Tests for simulation create — profile check, permission check."""

from uuid import uuid4
import pytest
from app.infra.simulation.create import create_simulation_impl
from app.infra.simulation.types import CreateSimulationApiRequest

pytestmark = pytest.mark.asyncio


async def test_create_raises_401_for_unknown_profile(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.simulation.create.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await create_simulation_impl(None, None, profile_id=uuid4(), request=CreateSimulationApiRequest(simulations=[]))
    assert exc_info.value.status_code == 401


async def test_create_raises_403_for_unauthorized_role(monkeypatch):
    from dataclasses import dataclass
    @dataclass
    class P:
        profiles_id: object = None
        role: str = "member"
        name: str = "U"
        group_id: object = None
        department_ids: list = None
        role_level: int = 3
        role_permissions: list = None
    async def mock_resolve(pool, pid, redis, **kw):
        return P(profiles_id=uuid4())
    monkeypatch.setattr("app.infra.simulation.create.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await create_simulation_impl(None, None, profile_id=uuid4(), request=CreateSimulationApiRequest(simulations=[]))
    assert exc_info.value.status_code == 403


async def test_create_detail_mentions_sign_in(monkeypatch):
    async def mock_resolve(pool, pid, redis, **kw):
        return None
    monkeypatch.setattr("app.infra.simulation.create.resolve_profile_identity_context", mock_resolve)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await create_simulation_impl(None, None, profile_id=uuid4(), request=CreateSimulationApiRequest(simulations=[]))
    assert "sign in" in exc_info.value.detail.lower()


# ============================================================================
# Cross-department assignment guard (write-side BOLA — mirrors scenario #226)
# ============================================================================

from fastapi import HTTPException
from dataclasses import dataclass as _assign_dataclass
from uuid import uuid4 as _assign_uuid4
_PROFILE_ID = _assign_uuid4()
from app.infra.simulation.types import CreateSimulationItem as _AssignItem


@_assign_dataclass
class _AssignDeptScopedProfile:
    """Non-top-level actor (level 1) holding simulation:create, scoped to one dept."""

    role_level = 1
    role_permissions = [("simulation", "create")]
    department_ids = None  # set per-instance

    def __init__(self, own_dept):
        self.department_ids = [own_dept]


@_assign_dataclass
class _AssignSuperadminProfile:
    """Top-level actor (level 0) — may assign any department."""

    role_level = 0
    role_permissions = [("simulation", "create")]
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
            "app.infra.simulation.create.resolve_profile_identity_context", fake_resolve,
        )
        monkeypatch.setattr(
            "app.infra.simulation.create.resolve_simulation_values", fake_values,
        )

    async def test_cross_department_create_denied(self, monkeypatch):
        own_dept = uuid4()
        foreign_dept = uuid4()
        self._patch_common(monkeypatch, _AssignDeptScopedProfile(own_dept))

        req = CreateSimulationApiRequest(
            simulations=[_AssignItem(department_ids=[foreign_dept])]
        )
        with pytest.raises(HTTPException) as exc_info:
            await create_simulation_impl(
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
            "app.infra.simulation.create.create_denormalized_snapshot", fake_snapshot,
        )

        req = CreateSimulationApiRequest(
            simulations=[_AssignItem(department_ids=[own_dept])]
        )
        with pytest.raises(RuntimeError, match="stop after guard"):
            await create_simulation_impl(
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
            "app.infra.simulation.create.create_denormalized_snapshot", fake_snapshot,
        )

        # Superadmin (level 0) may assign a department they do not "belong" to.
        req = CreateSimulationApiRequest(
            simulations=[_AssignItem(department_ids=[foreign_dept])]
        )
        with pytest.raises(RuntimeError, match="stop after guard"):
            await create_simulation_impl(
                _AssignPool(), object(), profile_id=_PROFILE_ID, request=req,
            )
        assert reached == [True]
