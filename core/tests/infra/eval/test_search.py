"""Tests for eval search — monkeypatch collaborators."""

from dataclasses import dataclass
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.eval.search import search_eval_impl

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
            "app.infra.eval.search.resolve_profile_identity_context", fake_resolve,
        )

        with pytest.raises(HTTPException) as exc_info:
            await search_eval_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, items=[],
            )
        assert exc_info.value.status_code == 401


class TestProfileResolved:
    async def test_profile_context_is_called(self, monkeypatch):
        called = []

        async def fake_resolve(*args, **kw):
            called.append(True)
            return _FakeProfile()

        monkeypatch.setattr(
            "app.infra.eval.search.resolve_profile_identity_context", fake_resolve,
        )

        # We expect downstream errors after profile resolution succeeds
        # but verify profile resolution was actually called
        try:
            await search_eval_impl(
                _FakePool(), object(), profile_id=_PROFILE_ID, items=[],
            )
        except Exception:
            pass  # downstream errors expected
        assert len(called) == 1


class TestImport:
    async def test_function_is_importable(self):
        assert callable(search_eval_impl)


# ── Department-scope clamp (authz-scope leak fix) ──────────────────────────────
# The LIST path previously returned every eval the artifact search matched and
# used the caller's role/dept ONLY for per-row can_edit/can_delete, leaking
# cross-department evals that the DETAIL sibling (``eval/get.py``) 403s. These
# tests pin the clamp: the impl now drops any eval the actor lacks
# ``has_access`` to (super-admin global, dept-less shared, otherwise overlap).

from datetime import UTC, datetime  # noqa: E402

from app.infra.eval.search import _search_eval_build  # noqa: E402
from app.infra.profile_identity_context import ProfileIdentityContext  # noqa: E402
from app.tools.artifacts.eval.types import GetEvalsResponse  # noqa: E402


def _eval_artifact(eval_id, department_ids):
    return GetEvalsResponse(
        id=eval_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        generated=False,
        mcp=False,
        active=True,
        name_ids=[],
        description_ids=[],
        department_ids=department_ids,
        flag_ids=[],
        model_ids=[],
        model_flag_ids=[],
        model_position_ids=[],
        model_rubric_ids=[],
        eval_ids=[],
    )


def _eval_profile(role_level, department_ids):
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


async def _run_eval_build(monkeypatch, *, actor, artifacts):
    """Drive ``_search_eval_build`` with stubbed collaborators; return the
    eval_ids that survive the actor-scope clamp + the response total_count."""
    import app.infra.eval.search as mod

    eval_ids = [a.id for a in artifacts]

    async def fake_resolve(pool, profile_id, redis, *a, **k):
        return actor

    async def fake_search_artifacts(conn, **kw):
        return (eval_ids, len(eval_ids))

    async def fake_soft_calls(conn, redis, **kw):
        return []

    async def fake_get_evals(conn, ids, **kw):
        by_id = {a.id: a for a in artifacts}
        return [by_id[i] for i in ids]

    async def fake_empty(*a, **k):
        return []

    monkeypatch.setattr(mod, "resolve_profile_identity_context", fake_resolve)
    monkeypatch.setattr(mod, "search_eval_artifacts", fake_search_artifacts)
    monkeypatch.setattr(
        "app.tools.entries.soft_calls.search.search_soft_calls", fake_soft_calls
    )
    monkeypatch.setattr(mod, "get_evals", fake_get_evals)
    monkeypatch.setattr(mod, "get_names", fake_empty)
    monkeypatch.setattr(mod, "get_descriptions", fake_empty)
    monkeypatch.setattr(mod, "get_flags", fake_empty)
    monkeypatch.setattr(mod, "search_departments", fake_empty)
    monkeypatch.setattr(mod, "search_flags", fake_empty)

    resp = await _search_eval_build(
        _FakePool(), object(), profile_id=_PROFILE_ID,
    )
    return {e.eval_id for e in resp.evals}, resp.total_count


class TestDepartmentScopeClamp:
    async def test_same_department_allowed_cross_department_denied(self, monkeypatch):
        dept_a, dept_b = uuid4(), uuid4()
        same = _eval_artifact(uuid4(), [dept_a])  # actor's dept → visible
        cross = _eval_artifact(uuid4(), [dept_b])  # other dept → hidden
        shared = _eval_artifact(uuid4(), [])  # dept-less → shared/visible
        actor = _eval_profile(role_level=2, department_ids=[dept_a])

        visible_ids, total = await _run_eval_build(
            monkeypatch, actor=actor, artifacts=[same, cross, shared]
        )

        assert same.id in visible_ids
        assert shared.id in visible_ids
        assert cross.id not in visible_ids  # leak closed
        assert total == 2  # count never advertises the hidden eval

    async def test_super_admin_sees_all(self, monkeypatch):
        dept_a, dept_b = uuid4(), uuid4()
        a = _eval_artifact(uuid4(), [dept_a])
        b = _eval_artifact(uuid4(), [dept_b])
        actor = _eval_profile(role_level=0, department_ids=[])

        visible_ids, total = await _run_eval_build(
            monkeypatch, actor=actor, artifacts=[a, b]
        )

        assert {a.id, b.id} == visible_ids
        assert total == 2
