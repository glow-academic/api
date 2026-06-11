"""A3 — ``test_start_impl`` writes run + call + test + benchmark-junction atomically.

The impl mints a run, a call, a ``test_entry`` and (when started from a
benchmark) a ``benchmark_test`` junction linking the test to its benchmark.
Pre-fix these autocommitted, so a failure on ``create_benchmark_test`` after
``create_test`` committed left an ORPHAN ``test_entry`` not linked to its
benchmark (it never surfaces under the benchmark). The fix wraps run + call +
test + junction in one ``conn.transaction()`` (analogue of attempt_start_impl).

``test_start_impl`` catches its own errors and emits ``test.start.error``
(no re-raise), so the test asserts on the unwound transaction + the emitted
error rather than a propagated exception.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

# Aliased import — bare ``test_*`` names get collected by pytest as test cases.
from app.infra.test.workflows import test_start_impl as start_test
from tests.infra._txn_fakes import TxnSpyConn, TxnSpyPool

pytestmark = pytest.mark.asyncio


def _patch_preamble(monkeypatch):
    async def _resolve_group(pool, redis, **kwargs):
        return SimpleNamespace(group_id=uuid4())

    async def _search_benchmarks(conn, redis, *, eval_ids, limit):
        return [SimpleNamespace(benchmark_id=uuid4(), dynamic=True)]

    async def _refresh(*args, **kwargs):
        return None

    async def _invalidate_tags(tags, *, redis):
        return None

    async def _search_invocations(conn, redis, *, benchmark_ids, limit):
        return [SimpleNamespace(id=uuid4())]

    monkeypatch.setattr("app.infra.group.resolve.resolve_group_impl", _resolve_group)
    monkeypatch.setattr(
        "app.tools.entries.benchmark.search.search_benchmarks", _search_benchmarks
    )
    monkeypatch.setattr("app.infra.test.refresh.refresh_test_impl", _refresh)
    monkeypatch.setattr("app.infra.invocation.refresh.refresh_invocation_impl", _refresh)
    monkeypatch.setattr("app.utils.cache.invalidate_tags.invalidate_tags", _invalidate_tags)
    monkeypatch.setattr(
        "app.tools.entries.invocation.search.search_invocations", _search_invocations
    )


def _capturing_emit(captured: list):
    async def _emit(events):
        captured.extend(events)

    return _emit


def _payload():
    return {
        "profile_id": str(uuid4()),
        "profiles_id": str(uuid4()),
        "session_id": str(uuid4()),
        "eval_id": str(uuid4()),
    }


async def test_benchmark_junction_failure_rolls_back_the_test(monkeypatch):
    """Fail ``create_benchmark_test`` — the already-written run/call/test must be
    inside the same transaction so they roll back (no orphan test_entry), and the
    flow surfaces a test.start.error (not a success)."""
    _patch_preamble(monkeypatch)
    conn = TxnSpyConn()
    writes: list = []

    async def _create_run(conn, redis, *, group_id, session_id):
        writes.append(("run", conn.in_txn))
        return SimpleNamespace(id=uuid4())

    async def _create_call(conn, redis, *, run_id, session_id):
        writes.append(("call", conn.in_txn))
        return SimpleNamespace(id=uuid4())

    async def _create_test(conn, redis, **kwargs):
        writes.append(("test", conn.in_txn))
        return SimpleNamespace(id=uuid4())

    async def _create_benchmark_test(conn, redis, **kwargs):
        raise RuntimeError("injected benchmark-junction failure")

    monkeypatch.setattr("app.tools.entries.runs.create.create_run", _create_run)
    monkeypatch.setattr("app.tools.entries.calls.create.create_call", _create_call)
    monkeypatch.setattr("app.tools.entries.test.create.create_test", _create_test)
    monkeypatch.setattr(
        "app.tools.entries.benchmark_test.create.create_benchmark_test",
        _create_benchmark_test,
    )

    captured: list = []
    data = _payload()
    await start_test(
        data, emit=_capturing_emit(captured), pool=TxnSpyPool(conn), redis=object()
    )

    # run/call/test all wrote inside the transaction → roll back with the junction.
    assert writes == [("run", True), ("call", True), ("test", True)]
    assert conn.txn_entered is True
    assert conn.txn_exit_exc is RuntimeError  # txn unwound → orphan test rolled back
    # No success result was published; an error was surfaced.
    assert "_result" not in data
    assert any(ev.event == "test.start.error" for ev in captured), captured


async def test_happy_start_commits_in_one_transaction(monkeypatch):
    _patch_preamble(monkeypatch)
    conn = TxnSpyConn()
    seen: dict[str, bool] = {}

    async def _create_run(conn, redis, *, group_id, session_id):
        seen["run"] = conn.in_txn
        return SimpleNamespace(id=uuid4())

    async def _create_call(conn, redis, *, run_id, session_id):
        seen["call"] = conn.in_txn
        return SimpleNamespace(id=uuid4())

    test_id = uuid4()

    async def _create_test(conn, redis, **kwargs):
        seen["test"] = conn.in_txn
        return SimpleNamespace(id=test_id)

    async def _create_benchmark_test(conn, redis, **kwargs):
        seen["junction"] = conn.in_txn
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr("app.tools.entries.runs.create.create_run", _create_run)
    monkeypatch.setattr("app.tools.entries.calls.create.create_call", _create_call)
    monkeypatch.setattr("app.tools.entries.test.create.create_test", _create_test)
    monkeypatch.setattr(
        "app.tools.entries.benchmark_test.create.create_benchmark_test",
        _create_benchmark_test,
    )

    captured: list = []
    data = _payload()
    await start_test(
        data, emit=_capturing_emit(captured), pool=TxnSpyPool(conn), redis=object()
    )

    assert seen == {"run": True, "call": True, "test": True, "junction": True}
    assert conn.txn_exit_exc is None
    assert data["_result"]["test_id"] == str(test_id)
