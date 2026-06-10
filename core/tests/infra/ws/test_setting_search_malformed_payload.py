"""Regression: WS ``setting.search`` must reject a malformed payload with a
clean ``setting.search.failed`` event, not an unhandled exception.

Every sibling ``*.search`` socket handler (``agent.search``,
``system.activity_search``, …) wraps ``Payload(**data)`` in a try/except and
emits a ``.failed`` validation event when the inbound payload is malformed.
``app.ws.setting.search.setting_search`` was the lone outlier: it spread the
raw socket payload straight into ``SettingSearchPayload(**data)`` with no
guard. A non-dict ``data`` makes ``**data`` raise ``TypeError`` and a
wrong-typed field raises a Pydantic ``ValidationError`` — either way the
exception aborts the handler and socket.io swallows it, so the client never
receives any ``.failed`` event (a silent hang with no feedback).

Pure handler-layer unit test: ``resolve_socket_identity`` and the global
pool/redis accessors are mocked, and the module-level ``internal_sio`` is
replaced with a recorder so we can assert the clean error event. No database
or live socket is required — validation happens before any DB access.
"""

from __future__ import annotations

import importlib
from typing import Any
from uuid import uuid4

import pytest

from app.infra.identity.resolve_identity import Identity

pytestmark = pytest.mark.asyncio

HANDLER_MODULE = "app.ws.setting.search"


def _make_identity() -> Identity:
    return Identity(
        profile_id=uuid4(),
        session_id=uuid4(),
        email="t@example.com",
        role="superadmin",
    )


class _RecordingBus:
    """Minimal stand-in for ``internal_sio`` that records emitted events."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def emit(self, event: str, payload: dict[str, Any]) -> None:
        self.events.append((event, payload))


def _wire(monkeypatch: pytest.MonkeyPatch, bus: _RecordingBus) -> Any:
    handler_mod = importlib.import_module(HANDLER_MODULE)
    identity = _make_identity()

    async def fake_resolve(sid: str) -> Identity:
        return identity

    monkeypatch.setattr(handler_mod, "resolve_socket_identity", fake_resolve)
    monkeypatch.setattr(handler_mod, "internal_sio", bus)

    # If validation is (incorrectly) skipped, the handler would reach the
    # audit wrapper — make that loudly fail so the test can't pass for the
    # wrong reason on a malformed payload.
    async def _should_not_run(*_a: Any, **_k: Any) -> Any:  # pragma: no cover
        raise AssertionError("audit wrapper reached — payload validation did not gate")

    monkeypatch.setattr(handler_mod, "run_artifact_operation_with_audit", _should_not_run)
    monkeypatch.setattr(handler_mod, "get_pool", lambda: object())
    monkeypatch.setattr(handler_mod, "get_redis_client", lambda: object())
    return handler_mod


async def test_ws_setting_search_rejects_non_dict_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-dict payload (``**data`` -> TypeError) -> clean failed event."""
    bus = _RecordingBus()
    handler_mod = _wire(monkeypatch, bus)

    # Pre-fix: ``SettingSearchPayload(**["x"])`` raises TypeError (unhandled).
    await handler_mod.setting_search("sid-1", ["x"])  # type: ignore[arg-type]

    assert len(bus.events) == 1
    event, payload = bus.events[0]
    assert event == "setting.search.failed"
    assert payload["error_type"] == "validation"
    assert payload["rooms"] == ["sid-1"]


async def test_ws_setting_search_rejects_wrong_typed_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A wrong-typed field (Pydantic ValidationError) -> clean failed event."""
    bus = _RecordingBus()
    handler_mod = _wire(monkeypatch, bus)

    # flag_search must be ``str | None``; a list trips Pydantic validation.
    await handler_mod.setting_search("sid-1", {"flag_search": ["not", "a", "str"]})

    assert len(bus.events) == 1
    event, payload = bus.events[0]
    assert event == "setting.search.failed"
    assert payload["error_type"] == "validation"


async def test_ws_setting_search_valid_payload_passes_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A well-formed payload validates and proceeds to the audit wrapper.

    Confirms the fix doesn't reject valid input — here we trip the audit
    sentinel, proving validation succeeded and no ``.failed`` was emitted.
    """
    bus = _RecordingBus()
    handler_mod = importlib.import_module(HANDLER_MODULE)
    identity = _make_identity()

    async def fake_resolve(sid: str) -> Identity:
        return identity

    monkeypatch.setattr(handler_mod, "resolve_socket_identity", fake_resolve)
    monkeypatch.setattr(handler_mod, "internal_sio", bus)
    monkeypatch.setattr(handler_mod, "get_pool", lambda: object())
    monkeypatch.setattr(handler_mod, "get_redis_client", lambda: object())

    reached: dict[str, bool] = {"hit": False}

    async def _sentinel(*_a: Any, **_k: Any) -> Any:
        reached["hit"] = True
        raise RuntimeError("stop after validation")

    monkeypatch.setattr(handler_mod, "run_artifact_operation_with_audit", _sentinel)

    # Validation passes and the handler reaches the audit sentinel; its
    # RuntimeError is swallowed by the centralized ws guard (app.infra.globals;
    # see test_ws_handler_error_containment), so we assert via the flag.
    await handler_mod.setting_search("sid-1", {"flag_search": "active"})

    assert reached["hit"] is True
    assert bus.events == []
