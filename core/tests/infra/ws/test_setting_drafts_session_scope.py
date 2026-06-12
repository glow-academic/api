"""D1 read-IDOR regression: the ``setting.drafts`` WS handler MUST forward the
caller's ``session_id`` to ``list_setting_drafts_impl``.

setting_drafts is the sole draft family with no profiles-connection table, so
its only ownership scope is the session. Pre-fix the handler passed only
``profile_id`` -> ``session_id=None`` -> the search WHERE collapsed to TRUE and
every authenticated socket received every user's secrets-bearing setting
drafts. This is a pure handler-layer unit test: ``resolve_socket_identity`` and
the audit wrapper are stubbed so we can capture exactly what kwargs the runner
invokes ``list_setting_drafts_impl`` with. No DB or live socket required.
"""

from __future__ import annotations

import importlib
from typing import Any
from uuid import uuid4

import pytest

from app.infra.identity.resolve_identity import Identity

pytestmark = pytest.mark.asyncio

HANDLER_MODULE = "app.ws.setting.drafts"


def _make_identity() -> Identity:
    return Identity(
        profile_id=uuid4(),
        session_id=uuid4(),
        email="t@example.com",
        role="superadmin",
    )


async def test_ws_setting_drafts_forwards_session_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner must call list_setting_drafts_impl with the caller's session_id."""
    handler_mod = importlib.import_module(HANDLER_MODULE)
    identity = _make_identity()

    async def fake_resolve(sid: str) -> Identity:
        return identity

    monkeypatch.setattr(handler_mod, "resolve_socket_identity", fake_resolve)
    monkeypatch.setattr(handler_mod, "get_pool", lambda: object())
    monkeypatch.setattr(handler_mod, "get_redis_client", lambda: object())

    captured: dict[str, Any] = {}

    async def fake_impl(*_a: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        return None

    monkeypatch.setattr(handler_mod, "list_setting_drafts_impl", fake_impl)

    # The audit wrapper just invokes the runner and returns its result.
    async def fake_audit(*_a: Any, runner: Any, **_k: Any) -> Any:
        return await runner()

    monkeypatch.setattr(handler_mod, "run_artifact_operation_with_audit", fake_audit)

    await handler_mod.setting_drafts("sid-1", {})

    assert captured.get("profile_id") == identity.profile_id
    # The load-bearing assertion: session scope IS forwarded (D1 fix).
    assert captured.get("session_id") == identity.session_id


async def test_ws_setting_drafts_no_identity_is_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unauthenticated socket -> handler returns without calling the impl."""
    handler_mod = importlib.import_module(HANDLER_MODULE)

    async def fake_resolve(sid: str) -> None:
        return None

    monkeypatch.setattr(handler_mod, "resolve_socket_identity", fake_resolve)

    async def _should_not_run(*_a: Any, **_k: Any) -> Any:  # pragma: no cover
        raise AssertionError("impl reached for an unauthenticated socket")

    monkeypatch.setattr(handler_mod, "list_setting_drafts_impl", _should_not_run)
    monkeypatch.setattr(handler_mod, "run_artifact_operation_with_audit", _should_not_run)

    await handler_mod.setting_drafts("sid-1", {})
