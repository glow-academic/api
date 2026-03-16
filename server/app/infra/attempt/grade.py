"""Internal handler: attempt_grade — canonical orchestration entry."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.attempt.grade_types import GradeAttemptRequest
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
from app.infra.attempt.client_types import AttemptGradePayload
from app.infra.websocket.attempt_types import AttemptErrorData
from app.tools.entries.attempt_grade.create import create_attempt_grade
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run

internal_sio = get_internal_sio()

DEFAULT_GRADE_RESOURCE_TYPES = [
    "feedbacks",
    "strengths",
    "improvements",
    "analyses",
    "highlights",
    "replacements",
]


class AttemptGradeInternalResult(BaseModel):
    chat_id: str
    grade_id: str | None = None
    score: int | None = None
    passed: bool | None = None


async def attempt_grade_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> AttemptGradeInternalResult:
    """Run canonical attempt grade orchestration for any surface."""
    sid = data.get("sid", "")
    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for attempt_grade")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for attempt_grade")

    # Accept either socket payload or richer HTTP payload.
    if "resource_types" in data or "score" in data or "feedbacks" in data:
        request = GradeAttemptRequest(**data)
        attempt_id = request.attempt_id
        chat_id = request.chat_id
        resource_types = request.resource_types or DEFAULT_GRADE_RESOURCE_TYPES
        score = request.score
        passed = request.passed
    else:
        payload = AttemptGradePayload(**data)
        attempt_id = payload.attempt_id
        chat_id = payload.chat_id
        resource_types = payload.resource_types or DEFAULT_GRADE_RESOURCE_TYPES
        score = None
        passed = None

    if chat_id is None:
        raise ValueError("chat_id is required for attempt_grade")

    async def _run() -> AttemptGradeInternalResult:
        rooms = [sid, f"attempt_{chat_id}"] if sid else []
        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="attempt",
            operation="grade",
            emit=emit or make_emit(),
            entity_id=attempt_id,
        )
        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        identity = await resolve_profile_identity_context(
            get_pool(),
            UUID(str(profile_id)),
            get_redis_client(),
            session_id=UUID(str(session_id)),
        )
        profiles_id = identity.profiles_id if identity else None

        async with get_pool().acquire() as conn:
            group_result = await create_group(conn, session_id=UUID(str(session_id)))
            run_result = await create_run(
                conn,
                session_id=UUID(str(session_id)),
                group_id=group_result.id,
                profiles_id=profiles_id,
            )
            call_result = await create_call(
                conn,
                run_id=run_result.id,
                session_id=UUID(str(session_id)),
            )
            grade_result = await create_attempt_grade(
                conn,
                chat_id=chat_id,
                call_id=call_result.id,
                run_id=run_result.id,
                time_taken=0,
                passed=passed or False,
                score=score or 0,
            )
            grade_id = str(grade_result.id) if grade_result.id else None

        await _emit(
            [
                internal_event(
                    "attempt_grade_start",
                    {
                        "sid": sid,
                        "chat_id": str(chat_id),
                        "grade_id": grade_id,
                        "rooms": rooms or None,
                    },
                ),
                internal_event(
                    "attempt_grade_complete",
                    {
                        "sid": sid,
                        "attempt_id": str(attempt_id),
                        "chat_id": str(chat_id),
                        "grade_id": grade_id,
                        "rooms": rooms or None,
                    },
                ),
                internal_event(
                    "generate",
                    {
                        "sid": sid,
                        "profile_id": str(profile_id),
                        "profiles_id": str(profiles_id) if profiles_id else None,
                        "session_id": str(session_id),
                        "artifact_types": [{"name": "attempt", "operation": "get"}],
                        "artifact_id": str(attempt_id),
                        "resource_types": resource_types,
                        "save": True,
                        "run_id": str(run_result.id),
                        "group_id": str(group_result.id),
                        "metadata": {
                            "attempt_id": str(attempt_id),
                            "chat_id": str(chat_id),
                            "grade_id": grade_id,
                            "grade_complete_emitted": True,
                        },
                    },
                ),
            ]
        )

        for event in recorded:
            if event.bus != "internal":
                continue
            if event.event == "attempt_error":
                error = AttemptErrorData(**event.data)
                raise ValueError(error.message)

        return AttemptGradeInternalResult(
            chat_id=str(chat_id),
            grade_id=grade_id,
            score=score,
            passed=passed,
        )

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="attempt",
        profile_id=UUID(str(profile_id)),
        operation="grade",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        entity_id=attempt_id,
        attempt_id=UUID(str(attempt_id)),
        response_model=AttemptGradeInternalResult,
    )


@internal_sio.on("attempt_grade")  # type: ignore
async def attempt_grade_handler(data: dict[str, Any]) -> None:
    await attempt_grade_internal_impl(data)
