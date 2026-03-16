"""Internal handler: test_run — canonical orchestration entry."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.infra.stream.socket_bridge import wrap_emit_with_stream_bridge
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.test.client_types import TestRunPayload
from app.infra.test.workflows import test_run_impl
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit
from app.infra.websocket.test_types import TestErrorData


class TestRunInternalResult(BaseModel):
    test_id: str
    invocation_id: str
    run_id: str


async def test_run_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestRunInternalResult:
    """Run canonical test run orchestration for any surface."""
    payload = TestRunPayload(**data)

    profile_id = data.get("profile_id")
    if not profile_id:
        raise ValueError("Missing profile_id for test_run")
    session_id = data.get("session_id")
    if not session_id:
        raise ValueError("Missing session_id for test_run")

    identity = await resolve_profile_identity_context(
        get_pool(),
        UUID(profile_id),
        get_redis_client(),
        session_id=UUID(session_id),
    )

    async def _run() -> TestRunInternalResult:
        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="test",
            operation="run",
            emit=emit or make_emit(),
            entity_id=payload.test_invocation_id,
        )
        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        await test_run_impl(
            {
                **data,
                "profiles_id": str(identity.profiles_id) if identity else None,
                "session_id": session_id,
            },
            emit=_emit,
            pool=get_pool(),
        )

        for event in recorded:
            if event.bus != "internal":
                continue
            if event.event == "test_run_started":
                return TestRunInternalResult(
                    test_id=event.data.get("test_id", ""),
                    invocation_id=event.data.get("test_invocation_id", ""),
                    run_id=event.data.get("run_id", ""),
                )
            if event.event == "test_error":
                error = TestErrorData(**event.data)
                raise ValueError(error.message)

        raise ValueError("Test run completed without a terminal event")

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="test",
        profile_id=UUID(profile_id),
        operation="run",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(session_id),
        entity_id=payload.test_invocation_id,
        test_id=payload.test_id,
        response_model=TestRunInternalResult,
    )
