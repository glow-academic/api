"""Tests for cohort search — monkeypatch collaborators."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.cohort.search import search_cohort_impl

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
            "app.infra.cohort.search.resolve_profile_identity_context", fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await search_cohort_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID,
            )
        assert exc_info.value.status_code == 401


class TestProfileResolved:
    async def test_profile_context_is_called(self, monkeypatch):
        called = []

        async def fake_resolve(*args, **kw):
            called.append(True)
            return _FakeProfile()

        monkeypatch.setattr(
            "app.infra.cohort.search.resolve_profile_identity_context", fake_resolve,
        )

        # We expect downstream errors after profile resolution succeeds
        # but verify profile resolution was actually called
        try:
            await search_cohort_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID,
            )
        except Exception:
            pass  # downstream errors expected
        assert len(called) == 1


class TestImport:
    async def test_function_is_importable(self):
        assert callable(search_cohort_impl)


# ── Department-scope clamp (authz-scope leak fix) ──────────────────────────────
# The LIST path previously returned every cohort the artifact search matched
# AND hydrated their member roster ``profile_ids``, leaking cross-department
# cohorts (and their members) that the DETAIL sibling (``cohort/get.py``) 403s.
# These tests pin the clamp: any cohort the actor lacks ``has_access`` to is
# dropped BEFORE its roster is collected (super-admin global, dept-less shared,
# otherwise overlap).

from datetime import UTC, datetime  # noqa: E402

from app.infra.cohort.search import _search_cohort_build  # noqa: E402
from app.infra.profile_identity_context import ProfileIdentityContext  # noqa: E402
from app.tools.artifacts.cohort.types import GetCohortsResponse  # noqa: E402


def _cohort_artifact(cohort_id, department_ids, profiles_ids):
    return GetCohortsResponse(
        id=cohort_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        generated=False,
        mcp=False,
        active=True,
        name_ids=[],
        description_ids=[],
        department_ids=department_ids,
        flag_ids=[],
        profiles_ids=profiles_ids,
        profile_persona_ids=[],
        simulation_ids=[],
        simulation_availability_ids=[],
        simulation_position_ids=[],
        cohort_ids=[],
    )


def _cohort_profile(role_level, department_ids):
    return ProfileIdentityContext(
        profiles_id=uuid4(),
        name="actor",
        role="instructional" if role_level else "superadmin",
        role_name="r",
        role_description="",
        role_artifacts=[],
        primary_email=None,
        emails=[],
        primary_department_id=None,
        department_ids=department_ids,
        settings_id=None,
        request_limit=None,
        request_limit_interval=None,
        is_active=True,
        role_level=role_level,
        role_permissions=[],
    )


async def _run_cohort_build(monkeypatch, *, actor, artifacts):
    """Drive ``_search_cohort_build`` with stubbed collaborators; return the
    surviving cohort_ids, the response total_count, and the set of roster
    profile_ids the response exposes (to prove the roster leak is closed)."""
    import app.infra.cohort.search as mod

    cohort_ids = [a.id for a in artifacts]

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_search_cohorts(conn, **kw):
        return (cohort_ids, len(cohort_ids))

    async def fake_soft_calls(conn, redis, **kw):
        return []

    async def fake_get_cohorts(conn, ids, **kw):
        by_id = {a.id: a for a in artifacts}
        return [by_id[i] for i in ids]

    async def fake_empty(*a, **k):
        return []

    monkeypatch.setattr(mod, "resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(mod, "search_cohorts", fake_search_cohorts)
    monkeypatch.setattr(
        "app.tools.entries.soft_calls.search.search_soft_calls", fake_soft_calls
    )
    monkeypatch.setattr(mod, "get_cohorts", fake_get_cohorts)
    monkeypatch.setattr(mod, "get_names", fake_empty)
    monkeypatch.setattr(mod, "get_profiles_resource", fake_empty)
    monkeypatch.setattr(mod, "get_simulations_resource", fake_empty)
    monkeypatch.setattr(mod, "get_departments", fake_empty)
    monkeypatch.setattr(mod, "search_profiles_resource", fake_empty)
    monkeypatch.setattr(mod, "search_simulations_resource", fake_empty)
    monkeypatch.setattr(mod, "search_departments", fake_empty)
    monkeypatch.setattr(mod, "search_flags", fake_empty)

    resp = await _search_cohort_build(
        _FakePool(), object(), profile_id=_PROFILE_ID,
    )
    surviving = {c.cohort_id for c in resp.cohorts}
    exposed_member_ids: set = set()
    for c in resp.cohorts:
        exposed_member_ids.update(c.profile_ids)
    return surviving, resp.total_count, exposed_member_ids


class TestDepartmentScopeClamp:
    async def test_cross_department_cohort_and_roster_hidden(self, monkeypatch):
        dept_a, dept_b = uuid4(), uuid4()
        member_a, member_b = uuid4(), uuid4()
        same = _cohort_artifact(uuid4(), [dept_a], [member_a])
        cross = _cohort_artifact(uuid4(), [dept_b], [member_b])  # other dept
        shared = _cohort_artifact(uuid4(), [], [])  # dept-less → shared
        actor = _cohort_profile(role_level=2, department_ids=[dept_a])

        surviving, total, exposed = await _run_cohort_build(
            monkeypatch, actor=actor, artifacts=[same, cross, shared]
        )

        assert same.id in surviving
        assert shared.id in surviving
        assert cross.id not in surviving  # cohort leak closed
        assert total == 2
        # The cross-department cohort's member must NOT appear in the roster.
        assert str(member_b) not in exposed
        assert str(member_a) in exposed

    async def test_super_admin_sees_all(self, monkeypatch):
        dept_a, dept_b = uuid4(), uuid4()
        a = _cohort_artifact(uuid4(), [dept_a], [uuid4()])
        b = _cohort_artifact(uuid4(), [dept_b], [uuid4()])
        actor = _cohort_profile(role_level=0, department_ids=[])

        surviving, total, _ = await _run_cohort_build(
            monkeypatch, actor=actor, artifacts=[a, b]
        )

        assert {a.id, b.id} == surviving
        assert total == 2
