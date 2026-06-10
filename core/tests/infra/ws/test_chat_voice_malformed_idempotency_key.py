"""Regression: WS ``attempt.chat_voice`` must reject a malformed idempotency_key
with a clean error ack, not an unhandled exception.

The HTTP route ``/attempt/chat_voice`` validates the body via
``ChatVoiceRequest`` (``idempotency_key: UUID | None``) at the Pydantic
boundary, so a malformed value is a clean 422 there. The WebSocket handler
``app.ws.attempt.chat.voice.attempt_chat_voice`` instead spreads the raw
socket payload straight into ``attempt_chat_voice_internal_impl``, which
coerces ``data["idempotency_key"]`` via ``uuid.UUID(...)`` with no error
handling. A malformed string (e.g. ``"not-a-uuid"``) raises ``ValueError``.

Pre-fix the handler had no try/except (unlike its sibling handlers
``attempt.chat_audio`` and ``attempt.draft``), so that ``ValueError``
propagated out of the socket handler unhandled — the client's emit-ack never
resolves (a hung voice-session start). Post-fix the handler returns a clean
``{"success": False, "error": ...}`` ack.

Pure handler-layer unit test: ``resolve_socket_identity`` and the global
pool/redis accessors are mocked, and ``run_artifact_operation_with_audit`` is
replaced with a passthrough that simply invokes the runner — so the real impl
runs and reaches the failing ``uuid.UUID(...)`` coercion (which happens before
any DB access). No database required.
"""

from __future__ import annotations

import importlib
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.infra.identity.resolve_identity import Identity

pytestmark = pytest.mark.asyncio

HANDLER_MODULE = "app.ws.attempt.chat.voice"
IMPL_MODULE = "app.infra.websocket.attempt.chat.voice"


def _make_identity() -> Identity:
    return Identity(
        profile_id=uuid4(),
        session_id=uuid4(),
        email="t@example.com",
        role="superadmin",
    )


async def _passthrough_audit(*_args: Any, runner: Any, **_kwargs: Any) -> Any:
    """Stand-in for run_artifact_operation_with_audit — just run the runner."""
    return await runner()


async def test_ws_chat_voice_rejects_malformed_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed idempotency_key over WS → clean error ack, not a crash."""
    handler_mod = importlib.import_module(HANDLER_MODULE)
    impl_mod = importlib.import_module(IMPL_MODULE)

    identity = _make_identity()

    async def fake_resolve(sid: str) -> Identity:
        return identity

    monkeypatch.setattr(handler_mod, "resolve_socket_identity", fake_resolve)
    monkeypatch.setattr(handler_mod, "get_pool", lambda: object())
    monkeypatch.setattr(handler_mod, "get_redis_client", lambda: object())
    # Run the impl directly through the runner so its UUID coercion executes.
    monkeypatch.setattr(handler_mod, "run_artifact_operation_with_audit", _passthrough_audit)
    monkeypatch.setattr(impl_mod, "get_redis_client", lambda: object())

    # Guard: if the malformed key somehow slipped past coercion, the impl would
    # next call group_attempt_impl — make that loudly fail so the test can't
    # pass for the wrong reason.
    async def _should_not_run(*_a: Any, **_k: Any) -> Any:  # pragma: no cover
        raise AssertionError("group_attempt_impl reached — coercion did not gate")

    monkeypatch.setattr(impl_mod, "group_attempt_impl", _should_not_run)

    data = {"chat_id": str(uuid4()), "idempotency_key": "not-a-uuid"}

    # Pre-fix: this raises ValueError (unhandled). Post-fix: clean error ack.
    result = await handler_mod.attempt_chat_voice("sid-1", data)

    assert isinstance(result, dict)
    assert result.get("success") is False
    assert "error" in result


async def test_ws_chat_voice_well_formed_uuid_passes_coercion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A well-formed idempotency_key coerces fine and proceeds past the gate.

    Confirms the fix doesn't reject valid input — a valid UUID string must get
    past the ``uuid.UUID(...)`` coercion (here we trip the group_attempt_impl
    sentinel, proving coercion succeeded).
    """
    handler_mod = importlib.import_module(HANDLER_MODULE)
    impl_mod = importlib.import_module(IMPL_MODULE)

    identity = _make_identity()

    async def fake_resolve(sid: str) -> Identity:
        return identity

    monkeypatch.setattr(handler_mod, "resolve_socket_identity", fake_resolve)
    monkeypatch.setattr(handler_mod, "get_pool", lambda: object())
    monkeypatch.setattr(handler_mod, "get_redis_client", lambda: object())
    monkeypatch.setattr(handler_mod, "run_artifact_operation_with_audit", _passthrough_audit)
    monkeypatch.setattr(impl_mod, "get_redis_client", lambda: object())

    reached: dict[str, bool] = {"hit": False}

    async def _sentinel(*_a: Any, **_k: Any) -> Any:
        reached["hit"] = True
        raise RuntimeError("stop after coercion")

    monkeypatch.setattr(impl_mod, "group_attempt_impl", _sentinel)

    data = {"chat_id": str(uuid4()), "idempotency_key": str(UUID(int=7))}

    # Well-formed UUID coerces; the handler then reaches the sentinel deeper in.
    # The sentinel's RuntimeError is now swallowed by the centralized ws guard
    # (app.infra.globals; see test_ws_handler_error_containment), so we assert
    # coercion succeeded via the sentinel flag rather than a propagated raise.
    await handler_mod.attempt_chat_voice("sid-1", data)

    assert reached["hit"] is True
