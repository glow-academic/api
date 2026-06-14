"""Unit coverage for the run-lifecycle event classifiers (R5).

``is_run_terminal`` decides when a run-scoped SSE stream (``glow … watch
<run_id>``) closes; ``is_non_droppable`` decides which frames the hub may never
shed on a full queue (S4). These two answers must DIVERGE for the per-agent
``agent_completed`` milestone:

  * R5 bug: ``agent_completed`` was a run TERMINAL → a run-scoped watcher closed
    on the FIRST agent's ``agent_completed`` (emitted BEFORE ``run_complete_impl``
    persists and before the canonical ``.completed``/``.failed``), truncating
    single-agent watches and — worse — in a multi-agent run never seeing a
    sibling's ``.failed`` and reporting phantom success (defeating S1).
  * Fix: ``agent_completed`` is NON-droppable (a progress milestone a consumer
    must still observe) but NOT a terminal (must not close the stream).
"""

from __future__ import annotations

from app.infra.stream.types import is_non_droppable, is_run_terminal


# ── is_run_terminal — only TRUE terminals close a run-scoped stream ───────────


def test_agent_completed_is_not_a_run_terminal():
    # R5: a per-agent progress milestone, NOT the end of the run.
    assert is_run_terminal("attempt.generate.agent_completed") is False


def test_true_terminals_are_run_terminal():
    for suffix in (
        "attempt.generate.completed",
        "attempt.generate.failed",
        "attempt.generate.error",
        "simulation.generate.media_complete",
        "simulation.generate.media_error",
    ):
        assert is_run_terminal(suffix) is True, suffix


def test_mid_run_complete_is_not_terminal():
    # ``.complete`` (no trailing "d") is a mid-run frame, must NOT match.
    assert is_run_terminal("attempt.generate.text.complete") is False


def test_run_terminal_handles_empty():
    assert is_run_terminal("") is False


# ── is_non_droppable — terminals PLUS load-bearing progress milestones ────────


def test_agent_completed_is_non_droppable():
    # R5: must survive a full-queue shed (a dropped per-agent milestone leaves a
    # multi-agent UI with a missing agent) — yet it is NOT a terminal above.
    assert is_non_droppable("attempt.generate.agent_completed") is True


def test_all_terminals_are_non_droppable():
    for suffix in (
        "attempt.generate.completed",
        "attempt.generate.failed",
        "attempt.generate.error",
        "simulation.generate.media_complete",
        "simulation.generate.media_error",
    ):
        assert is_non_droppable(suffix) is True, suffix


def test_progress_frame_is_droppable():
    assert is_non_droppable("attempt.generate.progress") is False
