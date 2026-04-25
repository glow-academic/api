"""Internal handler: test_invocation_complete — canonical per-invocation completion.

Mirrors ``/attempt/chat/complete``. Completion is a state transition only —
grading is a separate operation surfaced at ``/test/grade``. Call grade
before completing if you want a grade attached to the run.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.infra.stream.socket_bridge import wrap_emit_with_stream_bridge
from app.infra.test.client_types import TestInvocationCompletePayload
from app.infra.test.proceed import test_proceed_internal_impl
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import (
    EmitFn,
    SocketEvent,
    make_emit,
)
from app.infra.websocket.test_types import TestErrorData, TestProceedData


class TestInvocationCompleteInternalResult(BaseModel):
    invocation_id: str
    success: bool = True


async def test_invocation_complete_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestInvocationCompleteInternalResult:
    """Run canonical per-invocation completion. State transition only."""
    payload = TestInvocationCompletePayload(**data)
    sid = data.get("sid", "")

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for test_invocation_complete")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for test_invocation_complete")

    async def _run() -> TestInvocationCompleteInternalResult:
        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="test",
            operation="invocation_complete",
            emit=emit or make_emit(),
            entity_id=payload.test_invocation_id,
        )
        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        await test_proceed_internal_impl(
            TestProceedData(
                sid=sid,
                test_id=str(payload.test_id),
                completed_invocation_id=str(payload.test_invocation_id),
            ).model_dump(mode="json"),
            emit=_emit,
        )

        for event in recorded:
            if event.bus != "internal":
                continue
            if event.event.startswith("test.") and event.event.endswith(".error"):
                error = TestErrorData(**event.data)
                raise ValueError(error.message)

        return TestInvocationCompleteInternalResult(
            invocation_id=str(payload.test_invocation_id),
        )

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="test",
        profile_id=UUID(str(profile_id)),
        operation="invocation_complete",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        entity_id=payload.test_invocation_id,
        test_id=payload.test_id,
        response_model=TestInvocationCompleteInternalResult,
    )
