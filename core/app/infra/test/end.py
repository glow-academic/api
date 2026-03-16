"""Internal handler: test_end — canonical orchestration entry."""

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
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.test.client_types import TestEndPayload
from app.infra.test.proceed import test_proceed_internal_impl
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import (
    EmitFn,
    SocketEvent,
    internal_event,
    make_emit,
)
from app.infra.websocket.test_types import TestErrorData, TestProceedData
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.test_grade.create import create_test_grade


class TestEndInternalResult(BaseModel):
    invocation_id: str
    grade_id: str | None = None
    score: float | None = None
    passed: bool | None = None
    feedback: str | None = None


async def test_end_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestEndInternalResult:
    """Run canonical test end orchestration for any surface."""
    payload = TestEndPayload(**data)
    sid = data.get("sid", "")

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for test_end")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for test_end")

    async def _run() -> TestEndInternalResult:
        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="test",
            operation="end",
            emit=emit or make_emit(),
            entity_id=payload.test_invocation_id,
        )
        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        grade_id: str | None = None
        if payload.grade:
            identity = await resolve_profile_identity_context(
                get_pool(),
                UUID(str(profile_id)),
                get_redis_client(),
                session_id=UUID(str(session_id)),
            )
            profiles_id = identity.profiles_id if identity else None

            async with get_pool().acquire() as conn:
                group = await create_group(conn, session_id=UUID(str(session_id)))
                run = await create_run(
                    conn,
                    group_id=group.id,
                    session_id=UUID(str(session_id)),
                    profiles_id=profiles_id,
                )
                call = await create_call(
                    conn,
                    run_id=run.id,
                    session_id=UUID(str(session_id)),
                )
                grade = await create_test_grade(
                    conn,
                    invocation_id=payload.test_invocation_id,
                    call_id=call.id,
                    run_id=run.id,
                    time_taken=0,
                    passed=False,
                    score=0,
                )
                grade_id = str(grade.id)

            await _emit(
                [
                    internal_event(
                        "test_grade_start",
                        {
                            "sid": sid,
                            "test_id": str(payload.test_id),
                            "invocation_id": str(payload.test_invocation_id),
                            "test_invocation_id": str(payload.test_invocation_id),
                            "grade_id": grade_id,
                            "rooms": [sid, f"test_{payload.test_invocation_id}"]
                            if sid
                            else [f"test_{payload.test_invocation_id}"],
                        },
                    )
                ]
            )

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
            if event.event == "test_error":
                error = TestErrorData(**event.data)
                raise ValueError(error.message)

        return TestEndInternalResult(
            invocation_id=str(payload.test_invocation_id),
            grade_id=grade_id,
        )

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="test",
        profile_id=UUID(str(profile_id)),
        operation="end",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        entity_id=payload.test_invocation_id,
        test_id=payload.test_id,
        response_model=TestEndInternalResult,
    )
