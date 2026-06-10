"""FIX 1 — centralized ws-handler error containment.

socket.io runs each event handler as a fire-and-forget asyncio task with no
global ``on_error`` hook. The templated ws handler family
(create/update/delete/group/duplicate/...) all end in
``await run_artifact_operation_with_audit(...)``, which emits
``{artifact}.{op}.failed`` to the client and then RE-RAISES the underlying
error (so the shared wrapper can produce an HTTP error response on the route
side). On the ws side nothing caught that re-raise, so every failed mutation
leaked as "[ERROR] Task exception was never retrieved" + traceback.

#308 fixed this per-file for ``attempt.chat_message``. This generalizes the fix
across the whole family by guarding registration itself in
``app.infra.globals``: any handler attached via ``@sio.on(...)`` is wrapped so a
post-``.failed`` re-raise is logged at warning and swallowed instead of leaking.

Pure unit tests — no DB/redis/socket transport required. The first pair test
the registration mechanism directly; the third proves a real *templated* mutation
handler (``agent.create``) is covered with no per-file try/except.
"""

from __future__ import annotations

import importlib
from typing import Any
from uuid import uuid4

import pytest

from app.infra.globals import sio
from app.infra.identity.resolve_identity import Identity

pytestmark = pytest.mark.asyncio


async def test_sio_on_swallows_handler_exception() -> None:
    """A handler registered via ``@sio.on`` that raises must not propagate the
    exception out of the (guarded) registered callable — otherwise it leaks as
    an unretrieved-task exception."""

    @sio.on("test.ws_guard_boom")  # type: ignore[misc]
    async def _boom(sid: str, data: dict[str, Any]) -> None:
        raise ValueError("kaboom from inside the handler")

    registered = sio.handlers["/"]["test.ws_guard_boom"]

    # Must not raise; guard swallows and returns None.
    result = await registered("sid-1", {"x": 1})
    assert result is None


async def test_sio_on_is_transparent_on_success() -> None:
    """The guard must not change the happy path — a successful handler still
    returns its value to the emit-ack."""

    @sio.on("test.ws_guard_ok")  # type: ignore[misc]
    async def _ok(sid: str, data: dict[str, Any]) -> dict[str, Any]:
        return {"echo": data}

    registered = sio.handlers["/"]["test.ws_guard_ok"]
    result = await registered("sid-1", {"x": 1})
    assert result == {"echo": {"x": 1}}


class _PermissiveRequest:
    """Schema-agnostic stand-in so the test reaches the audit call regardless
    of the concrete ``CreateAgentApiRequest`` field requirements."""

    def __init__(self, **kwargs: Any) -> None:
        self._kwargs = kwargs

    def model_dump(self, *_a: Any, **_k: Any) -> dict[str, Any]:
        return self._kwargs


async def test_templated_create_handler_swallows_post_failed_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real templated mutation handler (``agent.create``) whose impl raises
    (re-raised by the audit wrapper AFTER it emits ``.failed``) must NOT leak —
    proving the centralized guard covers the create/update/delete/... family
    without any per-file try/except."""
    handler_mod = importlib.import_module("app.ws.agent.create")

    identity = Identity(
        profile_id=uuid4(),
        session_id=uuid4(),
        email="t@example.com",
        role="superadmin",
    )

    async def fake_resolve(_sid: str) -> Identity:
        return identity

    monkeypatch.setattr(handler_mod, "resolve_socket_identity", fake_resolve)
    monkeypatch.setattr(handler_mod, "get_pool", lambda: object())
    monkeypatch.setattr(handler_mod, "get_redis_client", lambda: object())
    monkeypatch.setattr(handler_mod, "CreateAgentApiRequest", _PermissiveRequest)

    emitted_failed = {"hit": False}

    async def exploding_audit(*_a: Any, **_k: Any) -> Any:
        # Mirror the real wrapper: emit ``.failed`` to the client, then re-raise.
        emitted_failed["hit"] = True
        raise ValueError("create_agent_impl blew up")

    monkeypatch.setattr(
        handler_mod, "run_artifact_operation_with_audit", exploding_audit
    )

    # The module-level handler name resolves to the *guarded* callable because
    # the centralized ``sio.on`` wrapper returns the guarded handler from the
    # decorator. Invoking it must not raise.
    result = await handler_mod.agent_create("sid-1", {"name": "x"})

    assert result is None
    assert emitted_failed["hit"] is True
