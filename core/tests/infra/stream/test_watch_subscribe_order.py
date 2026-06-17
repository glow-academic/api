"""report-19 HUB3: watch_runs_impl must subscribe to the hub BEFORE inspecting
state, so a run that reaches terminal in the gap between the snapshot read and
the subscribe is buffered (and drained) rather than missed → no spurious
timeout. (The prior order snapshotted first, then subscribed, opening that gap.)
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

import app.infra._watch as _watch
from app.infra._watch import watch_runs_impl
from app.infra.stream import hub
from app.infra.stream.hub import publish
from app.infra.stream.types import EventEnvelope

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_subscriptions():
    hub._SUBSCRIPTIONS.clear()
    yield
    hub._SUBSCRIPTIONS.clear()


async def test_mid_run_complete_is_not_treated_as_terminal():
    """HUB4 (report-19): a mid-run ``<artifact>.<op>.complete`` progress frame
    must NOT count as terminal (only ``.completed``/``.failed``/``.error``/
    media_* do). The prior private _TERMINAL_SUFFIXES wrongly included bare
    ``.complete`` → the watch returned 'completed' while the run was in flight.
    Now single-sourced from stream.types.is_run_terminal."""
    from app.infra._watch import _is_terminal

    def ev(et):
        return EventEnvelope(
            id="e", event_type=et, artifact="simulation", operation="generate",
            created_at=datetime.now(UTC), group_id=uuid4(), run_id=uuid4(),
        )

    assert _is_terminal(ev("simulation.generate.complete")) is False  # mid-run
    assert _is_terminal(ev("simulation.generate.completed")) is True
    assert _is_terminal(ev("simulation.generate.failed")) is True
    assert _is_terminal(ev("simulation.generate.error")) is True
    assert _is_terminal(ev("media_complete")) is True


def _terminal(group_id, run_id):
    return EventEnvelope(
        id=f"evt-{run_id}",
        event_type="persona.generate.completed",
        artifact="persona",
        operation="generate",
        created_at=datetime.now(UTC),
        group_id=group_id,
        run_id=run_id,
        payload={"resource_type": "personas"},
    )


async def test_terminal_fired_during_snapshot_is_not_missed(monkeypatch):
    """The exact HUB3 race: the run reaches terminal WHILE the snapshot is being
    read. Because we subscribe BEFORE the snapshot, the terminal event is
    buffered in our queue and drained → the watch returns promptly, not after
    the timeout. (With the old snapshot-then-subscribe order this event fired
    with no subscriber and the watch would hang to timeout.)"""
    group_id, run_id = uuid4(), uuid4()

    async def fake_snapshot(pool, gid, run_ids):
        # Simulate the run completing during the snapshot read: emit its
        # terminal as a side effect, and report nothing (DB saw it as not-yet-
        # terminal). Only a subscribe-FIRST watcher buffers this.
        await publish(_terminal(group_id, run_id))
        return []

    monkeypatch.setattr(_watch, "_snapshot_runs", fake_snapshot)

    resp = await asyncio.wait_for(
        watch_runs_impl(
            None,
            None,
            artifact_type="persona",
            group_id=group_id,
            run_id=run_id,
            wait_for_complete=True,
            timeout_seconds=10,
            profile_id=uuid4(),
        ),
        timeout=3.0,  # must return WELL before timeout_seconds if the race is closed
    )

    assert resp.timed_out is False
    assert any(r.run_id == run_id and r.status == "completed" for r in resp.runs)
    # Subscription cleaned up on exit.
    assert not hub._SUBSCRIPTIONS


async def test_wait_path_unsubscribes_on_terminal_snapshot(monkeypatch):
    """If the snapshot already shows the run terminal, the early return must
    still unsubscribe (no subscription leak from the subscribe-first reorder)."""
    from app.infra._watch import RunStatus

    group_id, run_id = uuid4(), uuid4()

    async def fake_snapshot(pool, gid, run_ids):
        return [RunStatus(run_id=run_id, status="completed")]

    monkeypatch.setattr(_watch, "_snapshot_runs", fake_snapshot)

    resp = await watch_runs_impl(
        None,
        None,
        artifact_type="persona",
        group_id=group_id,
        run_id=run_id,
        wait_for_complete=True,
        timeout_seconds=10,
        profile_id=uuid4(),
    )

    assert resp.timed_out is False
    assert [r.run_id for r in resp.runs] == [run_id]
    assert not hub._SUBSCRIPTIONS  # no leak
