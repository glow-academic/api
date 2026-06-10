"""FIX 3 — a ws disconnect records the activity row as inactive.

``create_activity`` writes ``active = NOT soft``. The disconnect handler's
``_mark_profile_inactive`` previously called it without ``soft``, so a logout
landed as ``active=true`` — inflating the activity/presence dashboard exactly
like a login. It must pass ``soft=True`` so the row is ``active=false``.

Pure unit test: the session lookup, pool, redis and ``create_activity`` are all
stubbed, so no DB/redis is required.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

import app.infra.globals as globals_mod
import app.tools.entries.activity.create as activity_create_mod
import app.ws.disconnect as disconnect_mod

pytestmark = pytest.mark.asyncio


class _FakeAcquire:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_a: Any) -> None:
        return None


class _FakePool:
    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire()


async def test_disconnect_records_activity_as_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = uuid4()
    profile_id = uuid4()

    async def fake_find_session(_sid: str) -> str:
        return str(session_id)

    monkeypatch.setattr(disconnect_mod, "find_session_by_socket", fake_find_session)
    monkeypatch.setattr(disconnect_mod, "get_redis_client", lambda: object())
    monkeypatch.setattr(globals_mod, "get_pool", lambda: _FakePool())

    captured: dict[str, Any] = {}

    async def fake_create_activity(_conn: Any, _redis: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(activity_create_mod, "create_activity", fake_create_activity)

    await disconnect_mod._mark_profile_inactive(str(profile_id), "sid-1")

    # The disconnect (went-inactive) row must be marked soft → active=false.
    assert captured.get("soft") is True, (
        "disconnect must record the activity row with soft=True (active=false) "
        "so logouts don't count as active"
    )
