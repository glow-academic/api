"""R6: ``run_generation_with_refresh`` must NOT double-emit ``.failed``.

On the blocking generate path (``wait_for_complete=True``) the runner's
``_run`` used to emit ``<artifact>.generate.failed`` AND re-raise — and the
re-raise bubbles to ``run_artifact_operation_with_audit``, which emits its
own ``<artifact>.generate.failed`` (with call_id/operation_key). That put
TWO ``.failed`` frames on the wire for a single error → double error toast /
double refresh on the group-wide watcher.

The audit wrapper is the single source of truth for the terminal (it also
owns ``.completed``), so on the blocking path the runner re-raises WITHOUT
emitting; on the background path (``wait_for_complete=False``) the audit
wrapper does not run, so the runner remains the failure channel and still
emits exactly one ``.failed``.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.infra.generation.runner as runner_mod
from app.infra.generation.runner import run_generation_with_refresh

pytestmark = pytest.mark.asyncio


class _RecordingSio:
    """Minimal stand-in for ``internal_sio`` that records emitted events."""

    def __init__(self) -> None:
        self.events: list[str] = []

    async def emit(self, event: str, payload: dict) -> None:  # noqa: D401
        self.events.append(event)


def _patch_failing_execute(monkeypatch) -> None:
    async def boom(*args, **kwargs):
        raise RuntimeError("forced generation failure")

    # ``execute_generation`` is a module-level import in runner.py.
    monkeypatch.setattr(runner_mod, "execute_generation", boom)


async def test_blocking_path_does_not_emit_failed_reraises(monkeypatch):
    """Blocking path: re-raises and emits ZERO ``.failed`` (audit wrapper owns it)."""
    _patch_failing_execute(monkeypatch)
    sio = _RecordingSio()
    prepared = SimpleNamespace(run_id=uuid4())

    with pytest.raises(RuntimeError, match="forced generation failure"):
        await run_generation_with_refresh(
            pool=None,
            redis=None,
            prepared=prepared,
            sid="sid-1",
            tool_soft=False,
            artifact_type="persona",
            refresh_fn=None,
            profile_id=uuid4(),
            session_id=uuid4(),
            group_id=uuid4(),
            internal_sio=sio,
            wait_for_complete=True,
        )

    # R6: exactly ZERO ``.failed`` on the blocking path — the bubbled
    # exception lets the audit wrapper emit the single terminal.
    assert sio.events.count("persona.generate.failed") == 0


async def test_background_path_emits_exactly_one_failed(monkeypatch):
    """Background path: audit wrapper does not run, so the runner emits exactly one ``.failed``."""
    _patch_failing_execute(monkeypatch)
    sio = _RecordingSio()
    prepared = SimpleNamespace(run_id=uuid4())

    # Background returns immediately; the failure lands on the spawned task.
    result = await run_generation_with_refresh(
        pool=None,
        redis=None,
        prepared=prepared,
        sid="sid-1",
        tool_soft=False,
        artifact_type="persona",
        refresh_fn=None,
        profile_id=uuid4(),
        session_id=uuid4(),
        group_id=uuid4(),
        internal_sio=sio,
        wait_for_complete=False,
    )
    assert result is None

    # Let the background task run to completion (it swallows the exception).
    import asyncio

    for _ in range(50):
        if sio.events.count("persona.generate.failed") >= 1:
            break
        await asyncio.sleep(0)

    assert sio.events.count("persona.generate.failed") == 1
