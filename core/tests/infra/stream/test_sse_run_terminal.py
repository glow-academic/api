"""Run-scoped SSE stream lifecycle (S4).

Two guarantees for a ``glow … watch <run_id>`` stream:
  1. it closes (clean EOF) when the run's terminal frame arrives, and
  2. it does NOT hang forever if that terminal frame is lost — an idle
     fallback timeout closes it instead.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.infra.stream import hub, sse
from app.infra.stream.hub import publish
from app.infra.stream.types import EventEnvelope

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_subscriptions():
    hub._SUBSCRIPTIONS.clear()
    yield
    hub._SUBSCRIPTIONS.clear()


def _event(group_id, run_id, event_type):
    return EventEnvelope(
        id=f"evt-{event_type}",
        event_type=event_type,
        artifact="simulation",
        operation="generate",
        created_at=datetime.now(UTC),
        group_id=group_id,
        run_id=run_id,
        payload={},
    )


async def _collect(response, *, max_frames: int = 50, timeout: float = 5.0):
    """Drain the StreamingResponse body iterator to completion (or guard)."""
    frames: list[str] = []
    agen = response.body_iterator

    async def _run():
        async for chunk in agen:
            frames.append(chunk)
            if len(frames) >= max_frames:
                break

    await asyncio.wait_for(_run(), timeout=timeout)
    return frames


async def test_run_scoped_stream_closes_on_terminal_frame():
    group_id, run_id = uuid4(), uuid4()
    response = await sse.build_artifact_stream_impl(
        group_id=group_id, artifact="simulation", run_id=run_id,
        keepalive_sec=0.05,
    )

    async def _emit():
        await asyncio.sleep(0.05)
        await publish(_event(group_id, run_id, "simulation.generate.completed"))

    emitter = asyncio.create_task(_emit())
    # If the terminal frame doesn't close the stream this would time out.
    frames = await _collect(response, timeout=3.0)
    await emitter
    assert any("simulation.generate.completed" in f for f in frames)


async def test_run_scoped_stream_does_not_hang_when_terminal_dropped(monkeypatch):
    """No terminal frame ever arrives — the idle fallback must close the stream
    so the watcher gets an EOF instead of looping on keep-alives forever."""
    group_id, run_id = uuid4(), uuid4()
    # Tiny fallback so the test is fast; real default is 600s.
    monkeypatch.setattr(sse, "MAX_RUN_STREAM_IDLE_SEC", 0.15)
    response = await sse.build_artifact_stream_impl(
        group_id=group_id, artifact="simulation", run_id=run_id,
        keepalive_sec=0.05,
    )
    # No events published at all → only keep-alives → fallback fires + closes.
    frames = await _collect(response, timeout=3.0)
    # Stream ended (iterator exhausted) within the timeout — and only emitted
    # keep-alives, never a data frame.
    assert frames  # got at least one keep-alive
    assert all(f.startswith(":") for f in frames)


async def test_busy_run_stream_idle_counter_resets(monkeypatch):
    """A live run that keeps emitting events for its run_id must NOT trip the
    idle fallback — each real event resets the idle counter."""
    group_id, run_id = uuid4(), uuid4()
    monkeypatch.setattr(sse, "MAX_RUN_STREAM_IDLE_SEC", 0.3)
    response = await sse.build_artifact_stream_impl(
        group_id=group_id, artifact="simulation", run_id=run_id,
        keepalive_sec=0.05,
    )

    async def _emit_then_terminal():
        # Emit several progress frames spaced under the idle ceiling, so the
        # counter keeps resetting and the fallback never fires; THEN terminal.
        for _ in range(4):
            await asyncio.sleep(0.1)
            await publish(_event(group_id, run_id, "simulation.generate.progress"))
        await publish(_event(group_id, run_id, "simulation.generate.completed"))

    emitter = asyncio.create_task(_emit_then_terminal())
    frames = await _collect(response, timeout=4.0)
    await emitter
    # The stream stayed open through all progress frames and closed only on the
    # real terminal — proving the idle fallback didn't cut a live run short.
    assert sum("simulation.generate.progress" in f for f in frames) == 4
    assert any("simulation.generate.completed" in f for f in frames)
