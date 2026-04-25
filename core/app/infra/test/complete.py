"""Internal handler: test_complete — canonical whole-test completion.

Mirrors AttemptComplete on the test side. Replaces the legacy end_all path.
Calls test_proceed_internal_impl with complete_all=True.
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
from app.infra.test.client_types import TestCompletePayload
from app.infra.test.proceed import test_proceed_internal_impl
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import (
    EmitFn,
    SocketEvent,
    make_emit,
)
from app.infra.websocket.test_types import TestErrorData, TestProceedData


class TestCompleteInternalResult(BaseModel):
    test_id: str
    success: bool = True


async def test_complete_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestCompleteInternalResult:
    """Run canonical whole-test completion."""
    payload = TestCompletePayload(**data)
    sid = data.get("sid", "")

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for test_complete")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for test_complete")

    async def _run() -> TestCompleteInternalResult:
        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="test",
            operation="complete",
            emit=emit or make_emit(),
            entity_id=payload.test_id,
        )
        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        await test_proceed_internal_impl(
            TestProceedData(
                sid=sid,
                test_id=str(payload.test_id),
                complete_all=True,
            ).model_dump(mode="json"),
            emit=_emit,
        )

        for event in recorded:
            if event.bus != "internal":
                continue
            if event.event.startswith("test.") and event.event.endswith(".error"):
                error = TestErrorData(**event.data)
                raise ValueError(error.message)

        return TestCompleteInternalResult(test_id=str(payload.test_id))

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="test",
        profile_id=UUID(str(profile_id)),
        operation="complete",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        entity_id=payload.test_id,
        test_id=payload.test_id,
        response_model=TestCompleteInternalResult,
    )
