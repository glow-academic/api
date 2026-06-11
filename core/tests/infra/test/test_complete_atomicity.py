"""A4 — ``_mark_all_invocations_complete`` bulk-completes N invocations atomically.

For every uncompleted invocation on a test, the helper mints run + call +
completion (3 writes). Pre-fix these autocommitted per-invocation, so a failure
on the k-th invocation left ``1..k-1`` committed-complete and the k-th half-built
(orphan run/call, no completion) — a partially-completed test with no all-or-
nothing. The fix wraps the whole loop in one ``conn.transaction()``.

Deps are stubbed as black boxes (the helper imports them locally, so the source
modules are patched) over a transaction-spy connection.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infra.test.complete import _mark_all_invocations_complete
from tests.infra._txn_fakes import TxnSpyConn

pytestmark = pytest.mark.asyncio


def _patch_helpers(monkeypatch, *, fail_on: int | None, writes: list):
    """fail_on = the 1-based invocation index whose completion write raises."""
    n_invs = 3
    invs = [
        SimpleNamespace(
            invocation_id=uuid4(),
            group_id=uuid4(),
            invocation_completed=False,
        )
        for _ in range(n_invs)
    ]

    async def _search(conn, redis, *, test_ids, limit):
        return invs, len(invs)

    async def _get_groups(conn, ids, redis):
        return [SimpleNamespace(session_id=uuid4())]

    async def _create_run(conn, redis, *, group_id, session_id):
        writes.append(("run", conn.in_txn))
        return SimpleNamespace(id=uuid4())

    async def _create_call(conn, redis, *, run_id, session_id):
        writes.append(("call", conn.in_txn))
        return SimpleNamespace(id=uuid4())

    completion_calls = {"n": 0}

    async def _create_completion(conn, redis, *, invocation_id, call_id, soft):
        completion_calls["n"] += 1
        if fail_on is not None and completion_calls["n"] == fail_on:
            raise RuntimeError("injected completion-write failure")
        writes.append(("completion", conn.in_txn))
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(
        "app.tools.entries.test_invocation.search.search_test_invocation_entries_internal",
        _search,
    )
    monkeypatch.setattr("app.tools.entries.groups.get.get_groups", _get_groups)
    monkeypatch.setattr("app.tools.entries.runs.create.create_run", _create_run)
    monkeypatch.setattr("app.tools.entries.calls.create.create_call", _create_call)
    monkeypatch.setattr(
        "app.tools.entries.test_invocation_completion.create.create_test_invocation_completion",
        _create_completion,
    )


async def test_mid_loop_failure_rolls_back_prior_completions(monkeypatch):
    """Fail the 2nd invocation's completion — the 1st invocation's run+call+
    completion must have run inside the transaction so they roll back together
    (no partially-completed test, no orphan run/call)."""
    writes: list = []
    _patch_helpers(monkeypatch, fail_on=2, writes=writes)
    conn = TxnSpyConn()

    with pytest.raises(RuntimeError, match="injected completion-write failure"):
        await _mark_all_invocations_complete(conn, uuid4())

    # The 1st invocation's writes landed BEFORE the failure — all inside the txn.
    assert writes  # at least the first invocation's writes ran
    assert all(in_txn for _, in_txn in writes), writes
    assert conn.txn_entered is True
    assert conn.txn_exit_exc is RuntimeError  # txn unwound → prior writes roll back


async def test_happy_bulk_complete_runs_in_one_transaction(monkeypatch):
    writes: list = []
    _patch_helpers(monkeypatch, fail_on=None, writes=writes)
    conn = TxnSpyConn()

    count, completion_ids = await _mark_all_invocations_complete(conn, uuid4())

    assert count == 3
    assert len(completion_ids) == 3
    assert all(in_txn for _, in_txn in writes)  # every write inside the txn
    assert conn.txn_exit_exc is None  # clean commit
