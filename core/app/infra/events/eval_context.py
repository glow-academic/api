"""Eval-mode contextvar.

Trace-driven benchmark runs flip a single contextvar at the top of the
run loop; ``create_soft_call`` reads it as the default for its ``eval``
kwarg. Every soft write inside the run is then tagged ``eval=true``
without threading the flag through 300+ callsites.

PEP 567 guarantees that ``asyncio.gather`` and ``asyncio.create_task``
inherit the caller's context, so per-agent fan-out in
``execute_with_emit`` works correctly: each parallel agent's task sees
the same eval flag set by the parent run.

Set via ``set_eval_mode(True)`` at the start of an eval run. Reset is
not strictly required for short-lived tasks; the contextvar dies with
the task. For long-lived servers a paranoid caller can wrap the run in
a ``try/finally`` and call ``set_eval_mode(False)`` on the way out.
"""

from __future__ import annotations

from contextvars import ContextVar

_EVAL_VAR: ContextVar[bool] = ContextVar("glow_eval_mode", default=False)


def set_eval_mode(value: bool) -> None:
    """Flip the eval flag for the current task + its descendants."""
    _EVAL_VAR.set(value)


def is_eval_mode() -> bool:
    """Return True iff this task is part of an eval run."""
    return _EVAL_VAR.get()
