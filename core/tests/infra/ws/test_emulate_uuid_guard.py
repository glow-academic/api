"""The ``profile.emulate`` WS handler must guard the UUID parse on raw client
input. An invalid ``target_profile_id`` previously flowed into the runner
lambda where ``UUID(...)`` raised inside the audit wrapper — surfacing as an
unretrieved-task traceback out of the fire-and-forget socket handler and
leaking the raw error into the payload. Every sibling handler guards this; this
one must too — emit a clean validation failure and never invoke the runner.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.ws.profile.emulate as emulate_mod

pytestmark = pytest.mark.asyncio


class _Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def emit(self, event: str, payload: dict) -> None:
        self.events.append((event, payload))


def _wire(monkeypatch, rec: _Recorder, ran: dict) -> None:
    async def fake_identity(_sid):
        return SimpleNamespace(
            profile_id=uuid4(), session_id=uuid4(), actor_profile_id=None
        )

    async def fake_run(*_a, **_k):
        ran["called"] = True

    monkeypatch.setattr(emulate_mod, "resolve_socket_identity", fake_identity)
    monkeypatch.setattr(emulate_mod, "internal_sio", rec)
    monkeypatch.setattr(emulate_mod, "run_artifact_operation_with_audit", fake_run)
    monkeypatch.setattr(emulate_mod, "get_pool", lambda: None)
    monkeypatch.setattr(emulate_mod, "get_redis_client", lambda: None)


async def test_invalid_uuid_emits_validation_and_skips_runner(monkeypatch):
    rec = _Recorder()
    ran = {"called": False}
    _wire(monkeypatch, rec, ran)

    await emulate_mod.profile_emulate("sid-1", {"target_profile_id": "not-a-uuid"})

    assert ran["called"] is False, "runner must not run on an invalid uuid"
    assert any(
        e == "profile.emulate.failed" and p.get("error_type") == "validation"
        for e, p in rec.events
    ), "a clean validation failure must be emitted"


async def test_valid_uuid_invokes_runner(monkeypatch):
    rec = _Recorder()
    ran = {"called": False}
    _wire(monkeypatch, rec, ran)

    await emulate_mod.profile_emulate(
        "sid-1", {"target_profile_id": str(uuid4())}
    )

    assert ran["called"] is True, "a valid uuid must reach the runner"
