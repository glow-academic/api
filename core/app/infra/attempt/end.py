"""Internal handler: attempt_end — canonical orchestration entry."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_internal_sio, get_pool, get_redis_client
from app.infra.stream.socket_bridge import wrap_emit_with_stream_bridge
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import (
    EmitFn,
    SocketEvent,
    internal_event,
    make_emit,
)
from app.infra.attempt.client_types import AttemptEndPayload
from app.infra.websocket.attempt_types import (
    AttemptGradeStartData,
    GenerateRequestData,
)
from app.tools.entries.attempt_grade.create import create_attempt_grade
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run

internal_sio = get_internal_sio()

GRADE_RESOURCE_TYPES = [
    "feedbacks",
    "strengths",
    "improvements",
    "analyses",
    "highlights",
    "replacements",
]


class AttemptEndInternalResult(BaseModel):
    chat_id: str
    is_attempt_finished: bool | None = None
    grade_id: str | None = None
    score: int | None = None
    passed: bool | None = None


async def attempt_end_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> AttemptEndInternalResult:
    """Run canonical attempt end orchestration for any surface."""
    from app.infra.attempt.proceed import attempt_proceed_internal_impl

    payload = AttemptEndPayload(**data)
    sid = data.get("sid", "")

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for attempt_end")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for attempt_end")

    profile_uuid = UUID(str(profile_id))
    session_uuid = UUID(str(session_id))

    async def _run(*, call_id: UUID | None = None) -> AttemptEndInternalResult:
        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="attempt",
            operation="end",
            emit=emit or make_emit(),
            entity_id=payload.attempt_id,
            call_id=call_id,
        )
        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        grade_id: str | None = None
        if payload.grade:
            identity = await resolve_profile_identity_context(
                get_pool(),
                profile_uuid,
                get_redis_client(),
                session_id=session_uuid,
            )
            profiles_id = identity.profiles_id if identity else None

            async with get_pool().acquire() as conn:
                group_result = await create_group(conn, session_id=session_uuid)
                run_result = await create_run(
                    conn,
                    session_id=session_uuid,
                    group_id=group_result.id,
                    profiles_id=profiles_id,
                )
                call_result = await create_call(
                    conn,
                    run_id=run_result.id,
                    session_id=session_uuid,
                )
                grade_result = await create_attempt_grade(
                    conn,
                    chat_id=payload.chat_id,
                    call_id=call_result.id,
                    run_id=run_result.id,
                    time_taken=0,
                    passed=False,
                    score=0,
                )
                grade_id = str(grade_result.id) if grade_result.id else None

            await _emit(
                [
                    internal_event(
                        "attempt_grade_start",
                        AttemptGradeStartData(
                            sid=sid,
                            chat_id=str(payload.chat_id),
                            grade_id=grade_id,
                        ).model_dump(mode="json"),
                    ),
                    internal_event(
                        "generate",
                        GenerateRequestData(
                            sid=sid,
                            profile_id=str(profile_id),
                            profiles_id=str(identity.profiles_id)
                            if identity and identity.profiles_id
                            else None,
                            session_id=str(session_id),
                            artifact_types=[{"name": "attempt", "operation": "get"}],
                            artifact_id=str(payload.attempt_id),
                            resource_types=GRADE_RESOURCE_TYPES,
                            save=True,
                            run_id=str(run_result.id),
                            group_id=str(group_result.id),
                            metadata={
                                "attempt_id": str(payload.attempt_id),
                                "chat_id": str(payload.chat_id),
                                "grade_id": grade_id,
                            },
                        ).model_dump(mode="json"),
                    ),
                ]
            )

        proceed_identity = await resolve_profile_identity_context(
            get_pool(),
            profile_uuid,
            get_redis_client(),
            session_id=session_uuid,
            attempt_id=payload.attempt_id,
        )
        group_id = proceed_identity.group_id if proceed_identity else None
        if group_id is None:
            raise ValueError(f"Group not found for attempt {payload.attempt_id}")

        await attempt_proceed_internal_impl(
            {
                "sid": sid,
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                "attempt_id": str(payload.attempt_id),
                "group_id": str(group_id),
                "completed_chat_id": str(payload.chat_id),
            },
            emit=_emit,
        )

        is_attempt_finished = any(
            event.bus == "internal" and event.event == "attempt_ended"
            for event in recorded
        )

        return AttemptEndInternalResult(
            chat_id=str(payload.chat_id),
            is_attempt_finished=is_attempt_finished,
            grade_id=grade_id,
        )

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="attempt",
        profile_id=profile_uuid,
        operation="end",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=session_uuid,
        entity_id=payload.attempt_id,
        attempt_id=payload.attempt_id,
        response_model=AttemptEndInternalResult,
    )


@internal_sio.on("attempt_end")  # type: ignore
async def attempt_end_handler(data: dict[str, Any]) -> None:
    await attempt_end_internal_impl(data)
