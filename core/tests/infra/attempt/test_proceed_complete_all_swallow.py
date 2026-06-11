"""SW2 — ``attempt_proceed_impl`` complete_all must not claim all-complete when a
per-scenario completion write failed.

The ``complete_all`` bridge loop writes a completion per scenario, then emits
``attempt.complete.completed`` with ``all_scenarios_complete=True``. Pre-fix the
per-scenario write was wrapped in ``except Exception: pass`` —
``create_attempt_chat_completion`` is idempotent (ON CONFLICT DO UPDATE, never
raises on a duplicate), so the bare ``pass`` only swallowed REAL DB/connection
failures, then went on to falsely report every scenario complete. The fix lets a
real failure propagate to the outer handler (emits ``attempt.proceed.error``) so
the all-complete claim is never emitted on a failed write.

Deps stubbed as black boxes over a fake pool.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.infra.attempt.workflows import attempt_proceed_impl
from tests.infra._txn_fakes import TxnSpyConn, TxnSpyPool

pytestmark = pytest.mark.asyncio


def _capturing_emit(captured: list):
    async def _emit(events):
        captured.extend(events)

    return _emit


def _patch_loop(monkeypatch, *, completion_side_effect):
    async def _create_run(conn, redis, *, group_id, session_id):
        return SimpleNamespace(id=uuid4())

    async def _search_bridges(conn, redis, *, attempt_ids, limit):
        return [
            SimpleNamespace(attempt_chat_id=uuid4()),
            SimpleNamespace(attempt_chat_id=uuid4()),
        ]

    async def _refresh(*args, **kwargs):
        return None

    monkeypatch.setattr("app.tools.entries.runs.create.create_run", _create_run)
    monkeypatch.setattr(
        "app.tools.entries.attempt_chat_bridge.search.search_attempt_chat_bridges",
        _search_bridges,
    )
    monkeypatch.setattr(
        "app.tools.entries.attempt_chat_completion.create.create_attempt_chat_completion",
        completion_side_effect,
    )
    monkeypatch.setattr("app.infra.attempt.refresh.refresh_attempt_impl", _refresh)


def _payload():
    return {
        "sid": "sid-1",
        "attempt_id": str(uuid4()),
        "group_id": str(uuid4()),
        "complete_all": True,
    }


async def _invoke(captured, monkeypatch):
    return await attempt_proceed_impl(
        _payload(),
        emit=_capturing_emit(captured),
        pool=TxnSpyPool(TxnSpyConn()),
        redis=object(),
        profile_id=str(uuid4()),
        session_id=str(uuid4()),
    )


async def test_failed_scenario_write_does_not_emit_all_complete(monkeypatch):
    """A real per-scenario completion failure must surface as a proceed.error and
    must NOT emit all_scenarios_complete=True."""

    async def _failing(conn, redis, *, chat_id, session_id):
        raise RuntimeError("injected scenario completion failure")

    _patch_loop(monkeypatch, completion_side_effect=_failing)
    captured: list = []
    await _invoke(captured, monkeypatch)

    types = [ev.event for ev in captured]
    # The false "all scenarios complete" success is NOT emitted ...
    assert "attempt.complete.completed" not in types, captured
    # ... and the failure is surfaced instead.
    assert "attempt.proceed.error" in types, captured


async def test_all_scenarios_persist_then_emit_all_complete(monkeypatch):
    """When every completion write succeeds, all_scenarios_complete=True is emitted."""
    calls = {"n": 0}

    async def _ok(conn, redis, *, chat_id, session_id):
        calls["n"] += 1
        return SimpleNamespace(id=uuid4(), active=True)

    _patch_loop(monkeypatch, completion_side_effect=_ok)
    captured: list = []
    await _invoke(captured, monkeypatch)

    assert calls["n"] == 2  # both scenarios written
    completed = [ev for ev in captured if ev.event == "attempt.complete.completed"]
    assert len(completed) == 1
    assert completed[0].data["all_scenarios_complete"] is True
