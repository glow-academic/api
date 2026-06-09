"""Regression: WS ``attempt.chat_message`` must not leak an unretrieved-task
exception when the message fails server-side.

``run_artifact_operation_with_audit`` emits ``attempt.chat_message.failed`` to
the client and THEN re-raises the runner's original error (e.g. a bad chat_id
that violates ``attempt_message_entry``'s FK, or a missing persona). socket.io
runs each event handler as a fire-and-forget task, so before the fix that
re-raised exception escaped the handler and surfaced as
"[ERROR] Task exception was never retrieved" with a full traceback in the
server log — even though the client had already been told via ``.failed``.

The handler now swallows the post-``.failed`` exception (logged at warning) so
no unretrieved-task traceback leaks. The client-facing ``.failed`` emission is
owned by the audit wrapper and is intentionally left untouched.

Pure handler-layer unit test: ``resolve_socket_identity``, the global
pool/redis accessors, the voice-session lookup, ``resolve_group_impl`` and
``run_artifact_operation_with_audit`` are all mocked, so no DB/redis/socket is
required. Mirrors ``test_chat_voice_malformed_idempotency_key``'s style.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.infra.identity.resolve_identity import Identity

pytestmark = pytest.mark.asyncio

HANDLER_MODULE = "app.ws.attempt.message"


def _make_identity() -> Identity:
    return Identity(
        profile_id=uuid4(),
        session_id=uuid4(),
        email="t@example.com",
        role="superadmin",
    )


def _wire_common(monkeypatch: pytest.MonkeyPatch, handler_mod: Any) -> None:
    """Stub the handler's dependencies up to the audit call."""
    identity = _make_identity()

    async def fake_resolve(sid: str) -> Identity:
        return identity

    async def fake_group(*_a: Any, **_k: Any) -> Any:
        return SimpleNamespace(group_id=uuid4())

    monkeypatch.setattr(handler_mod, "resolve_socket_identity", fake_resolve)
    monkeypatch.setattr(handler_mod, "get_pool", lambda: object())
    monkeypatch.setattr(handler_mod, "get_redis_client", lambda: object())
    # No active voice session → take the standard text pipeline.
    monkeypatch.setattr(handler_mod, "get_session_by_chat_id", lambda _cid: None)
    monkeypatch.setattr(handler_mod, "resolve_group_impl", fake_group)


async def test_ws_chat_message_swallows_post_failed_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A runner error (re-raised by the audit wrapper after emitting
    ``.failed``) must NOT propagate out of the socket handler — otherwise it
    leaks as an unretrieved-task exception."""
    handler_mod = importlib.import_module(HANDLER_MODULE)
    _wire_common(monkeypatch, handler_mod)

    emitted_failed = {"hit": False}

    async def exploding_audit(*_a: Any, **_k: Any) -> Any:
        # Stand-in for the real wrapper: it emits ``.failed`` to the client and
        # then re-raises the runner's original error.
        emitted_failed["hit"] = True
        raise ValueError(
            'insert or update on table "attempt_message_entry" violates '
            "foreign key constraint"
        )

    monkeypatch.setattr(
        handler_mod, "run_artifact_operation_with_audit", exploding_audit
    )

    data = {"chat_id": str(uuid4()), "text": "hello", "persona_id": str(uuid4())}

    # Pre-fix: this ValueError propagated out of the fire-and-forget handler
    # task → "Task exception was never retrieved". Post-fix: swallowed, None.
    result = await handler_mod.attempt_message("sid-1", data)

    assert result is None
    assert emitted_failed["hit"] is True


async def test_ws_chat_message_success_returns_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The swallow path must not change the happy path: a successful audit
    call still returns its result dict to the emit-ack."""
    handler_mod = importlib.import_module(HANDLER_MODULE)
    _wire_common(monkeypatch, handler_mod)

    expected = {"success": True, "message_id": str(uuid4()), "content_ids": []}

    async def ok_audit(*_a: Any, **_k: Any) -> Any:
        return expected

    monkeypatch.setattr(handler_mod, "run_artifact_operation_with_audit", ok_audit)

    data = {"chat_id": str(uuid4()), "text": "hello", "persona_id": str(uuid4())}
    result = await handler_mod.attempt_message("sid-1", data)

    assert result == expected
