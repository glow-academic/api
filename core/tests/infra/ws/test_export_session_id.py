"""Regression test for #84 — WS export handlers must thread session_id.

The 12 file-modality WS export handlers persist an upload via
``create_upload`` → ``INSERT uploads_entry(session_id, ...)`` where
``session_id`` is ``NOT NULL``. The handler obtains the caller identity from
``resolve_socket_identity`` (which always carries ``identity.session_id``) and
MUST forward it into ``export_<artifact>_impl(...)``. Previously these handlers
omitted it, so the impl defaulted ``session_id=None`` and the INSERT raised
``NotNullViolationError`` (500 on every WS file-modality export).

These are pure handler-layer unit tests: the impl, the audit runner, and the
global pool/redis accessors are all mocked, so no database is required. The
test captures the kwargs the handler passes into the impl and asserts
``session_id`` equals the identity's ``session_id``. It fails on the pre-fix
code (no ``session_id`` kwarg) and passes after.
"""

from __future__ import annotations

import importlib
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.infra.identity.resolve_identity import Identity

pytestmark = pytest.mark.asyncio

T = TypeVar("T")

# (handler module, handler coroutine name, impl symbol name in that module)
_HANDLERS = [
    ("app.ws.agent.export", "agent_export", "export_agent_impl"),
    ("app.ws.cohort.export", "cohort_export", "export_cohort_impl"),
    ("app.ws.department.export", "department_export", "export_department_impl"),
    ("app.ws.eval.export", "eval_export", "export_eval_impl"),
    ("app.ws.field.export", "field_export", "export_field_impl"),
    ("app.ws.model.export", "model_export", "export_model_impl"),
    ("app.ws.parameter.export", "parameter_export", "export_parameter_impl"),
    ("app.ws.persona.export", "persona_export", "export_persona_impl"),
    ("app.ws.provider.export", "provider_export", "export_provider_impl"),
    ("app.ws.setting.export", "setting_export", "export_setting_impl"),
    ("app.ws.simulation.export", "simulation_export", "export_simulation_impl"),
    ("app.ws.tool.export", "tool_export", "export_tool_impl"),
]


def _make_identity(session_id: UUID) -> Identity:
    return Identity(
        profile_id=uuid4(),
        session_id=session_id,
        email="t@example.com",
        role="superadmin",
    )


@pytest.mark.parametrize(("module_path", "handler_name", "impl_name"), _HANDLERS)
async def test_ws_export_forwards_session_id(
    monkeypatch: pytest.MonkeyPatch,
    module_path: str,
    handler_name: str,
    impl_name: str,
) -> None:
    """Each file-modality WS export handler forwards identity.session_id."""
    mod = importlib.import_module(module_path)
    session_id = uuid4()
    identity = _make_identity(session_id)

    # Identity comes from the socket store; return a real Identity.
    async def fake_resolve(sid: str) -> Identity:
        return identity

    monkeypatch.setattr(mod, "resolve_socket_identity", fake_resolve)

    # Avoid touching real globals.
    monkeypatch.setattr(mod, "get_pool", lambda: object())
    monkeypatch.setattr(mod, "get_redis_client", lambda: object())

    # Capture the kwargs the handler passes into the export impl.
    impl_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(mod, impl_name, impl_mock)

    # The audit wrapper normally drives caching/audit; here just run the
    # handler-built runner so we can inspect the impl call it produces.
    async def fake_audit(
        pool: Any,
        redis: Any,
        *,
        runner: Callable[[], Awaitable[T]],
        **kwargs: Any,
    ) -> T:
        return await runner()

    monkeypatch.setattr(mod, "run_artifact_operation_with_audit", fake_audit)

    handler = getattr(mod, handler_name)
    await handler("sid-1", {})

    assert impl_mock.await_count == 1, f"{impl_name} not invoked"
    call_kwargs = impl_mock.await_args.kwargs
    assert "session_id" in call_kwargs, (
        f"{handler_name} did not forward session_id into {impl_name} "
        "(#84: would default to None → NotNull on uploads_entry)"
    )
    assert call_kwargs["session_id"] == session_id
    # Sanity: profile_id is still threaded through unchanged.
    assert call_kwargs["profile_id"] == identity.profile_id
