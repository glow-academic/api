"""A1 — ``create_grade_impl`` writes the audit call + the grade atomically.

``create_grade_impl`` mints a ``calls_entry`` (for audit linkage) and then a
``test_grade_entry`` whose ``call_id`` FKs that call. Pre-fix these two writes
autocommitted independently, so a failure on the grade write left an ORPHAN
``calls_entry`` with no grade (and the call's cache write-back already ahead of
the DB). The fix wraps both in one ``conn.transaction()``.

Deps are stubbed as black boxes (mirrors ``test_grade_pass_points``), with a
transaction-spy connection so the test proves the orphan-prone call write ran
inside the transaction that unwinds on the grade-write failure.
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.infra.test.grade as grade_mod
from app.infra.test.grade import create_grade_impl
from tests.infra._txn_fakes import TxnSpyConn, TxnSpyPool

pytestmark = pytest.mark.asyncio


def _patch_reads(monkeypatch):
    inv = SimpleNamespace(
        rubric_id=uuid4(),
        test_id=None,  # run_id supplied via kwargs → skip the test→call chain
        invocation_created_at=datetime.now(UTC),
    )
    rubric = SimpleNamespace(total_points=10, pass_points=5)

    async def _get_test_invocations(conn, ids, redis):
        return [inv]

    async def _get_rubrics(conn, ids, redis):
        return [rubric]

    async def _refresh_test_impl(pool, redis, **kwargs):
        return None

    async def _invalidate_tags(tags, *, redis):
        return None

    # Authz (T1) is exercised in test_test_mutation_authz_class; stub it here so
    # this atomicity test isn't coupled to the ownership-resolution chain.
    async def _resolve(pool, profile_id, redis, *a, **k):
        return SimpleNamespace(profiles_id=profile_id, role="superadmin")

    async def _enforce(pool, redis, **kwargs):
        return None

    monkeypatch.setattr(grade_mod, "resolve_profile_identity_context", _resolve)
    monkeypatch.setattr(grade_mod, "enforce_test_access_by_invocation", _enforce)
    monkeypatch.setattr(grade_mod, "get_test_invocations", _get_test_invocations)
    monkeypatch.setattr(grade_mod, "get_rubrics", _get_rubrics)
    monkeypatch.setattr(grade_mod, "refresh_test_impl", _refresh_test_impl)
    monkeypatch.setattr(grade_mod, "invalidate_tags", _invalidate_tags)


async def test_grade_write_failure_rolls_back_the_audit_call(monkeypatch):
    """Inject a failure on the grade write — the already-written audit call must
    be inside the same transaction so it rolls back (no orphan calls_entry)."""
    _patch_reads(monkeypatch)
    conn = TxnSpyConn()

    call_ran_in_txn: list[bool] = []

    async def _create_call(conn, redis, *, run_id, session_id):
        # The orphan-prone write — must run INSIDE the transaction.
        call_ran_in_txn.append(conn.in_txn)
        return SimpleNamespace(id=uuid4())

    async def _create_test_grade(conn, redis, **kwargs):
        raise RuntimeError("injected grade-write failure")

    monkeypatch.setattr(grade_mod, "create_call", _create_call)
    monkeypatch.setattr(grade_mod, "create_test_grade", _create_test_grade)

    with pytest.raises(RuntimeError, match="injected grade-write failure"):
        await create_grade_impl(
            TxnSpyPool(conn),
            redis=object(),
            profile_id=uuid4(),
            session_id=uuid4(),
            invocation_id=uuid4(),
            score=5,
            run_id=uuid4(),
        )

    assert call_ran_in_txn == [True]  # audit call wrote inside the transaction
    assert conn.txn_entered is True
    assert conn.txn_exit_exc is RuntimeError  # txn unwound → call rolled back


async def test_grade_happy_path_commits_both_in_one_transaction(monkeypatch):
    _patch_reads(monkeypatch)
    conn = TxnSpyConn()
    where_ran: dict[str, bool] = {}

    async def _create_call(conn, redis, *, run_id, session_id):
        where_ran["call"] = conn.in_txn
        return SimpleNamespace(id=uuid4())

    async def _create_test_grade(conn, redis, **kwargs):
        where_ran["grade"] = conn.in_txn
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(grade_mod, "create_call", _create_call)
    monkeypatch.setattr(grade_mod, "create_test_grade", _create_test_grade)

    result = await create_grade_impl(
        TxnSpyPool(conn),
        redis=object(),
        profile_id=uuid4(),
        session_id=uuid4(),
        invocation_id=uuid4(),
        score=5,
        run_id=uuid4(),
    )

    assert result["success"] is True
    assert where_ran == {"call": True, "grade": True}  # both in one txn
    assert conn.txn_exit_exc is None  # clean commit
