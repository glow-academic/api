"""Regression test for the rubric ``pass_points`` NULL guard in create_grade.

``create_grade_impl`` reads ``pass_points`` straight off the rubric, which may
be NULL in the DB. The downstream ``passed = score >= pass_points if
pass_points > 0 else score > 0`` evaluates ``pass_points > 0`` first — and
``None > 0`` raises ``TypeError``. The fix coalesces to ``0`` (mirroring the
sibling ``chat_grade.py`` guard) so a NULL threshold falls through to the
``score > 0`` branch instead of crashing.

Dependencies are passed/stubbed as black boxes so this exercises the real
arithmetic path without a DB.
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.infra.test.grade as grade_mod
from app.infra.test.grade import create_grade_impl

pytestmark = pytest.mark.asyncio


class _FakeAcquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakeTransaction:
    """No-op stand-in for ``conn.transaction()`` (A1 wraps the grade write
    in a transaction; the fake conn must honor that interface)."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeConn:
    def transaction(self):
        return _FakeTransaction()


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquire(self._conn)


async def test_create_grade_does_not_raise_on_null_pass_points(monkeypatch):
    rubric_id = uuid4()
    invocation_id = uuid4()
    run_id = uuid4()

    inv = SimpleNamespace(
        rubric_id=rubric_id,
        test_id=None,
        invocation_created_at=datetime.now(UTC),
    )
    # The rubric carries a NULL pass threshold — the bug trigger.
    rubric = SimpleNamespace(total_points=10, pass_points=None)

    async def _get_test_invocations(conn, ids, redis):
        return [inv]

    async def _get_rubrics(conn, ids, redis):
        return [rubric]

    async def _create_call(conn, redis, *, run_id, session_id):
        return SimpleNamespace(id=uuid4())

    async def _create_test_grade(conn, redis, **kwargs):
        return SimpleNamespace(id=uuid4())

    async def _refresh_test_impl(pool, redis, **kwargs):
        return None

    async def _invalidate_tags(tags, *, redis):
        return None

    # Authz (T1) is exercised in test_test_mutation_authz_class; stub it here so
    # this arithmetic test isn't coupled to the ownership-resolution chain.
    async def _resolve(pool, profile_id, redis, *a, **k):
        return SimpleNamespace(profiles_id=profile_id, role="superadmin")

    async def _enforce(pool, redis, **kwargs):
        return None

    monkeypatch.setattr(grade_mod, "resolve_profile_identity_context", _resolve)
    monkeypatch.setattr(grade_mod, "enforce_test_access_by_invocation", _enforce)
    monkeypatch.setattr(grade_mod, "get_test_invocations", _get_test_invocations)
    monkeypatch.setattr(grade_mod, "get_rubrics", _get_rubrics)
    monkeypatch.setattr(grade_mod, "create_call", _create_call)
    monkeypatch.setattr(grade_mod, "create_test_grade", _create_test_grade)
    monkeypatch.setattr(grade_mod, "refresh_test_impl", _refresh_test_impl)
    monkeypatch.setattr(grade_mod, "invalidate_tags", _invalidate_tags)

    pool = _FakePool(conn=_FakeConn())

    # score=5 with pass_points=None: pre-fix this raised TypeError on `None > 0`.
    result = await create_grade_impl(
        pool,
        redis=object(),
        profile_id=uuid4(),
        session_id=uuid4(),
        invocation_id=invocation_id,
        score=5,
        run_id=run_id,
    )

    assert result["success"] is True
    assert result["score"] == 5
    # NULL threshold → coalesced to 0 → falls through to `score > 0` → passed.
    assert result["passed"] is True
