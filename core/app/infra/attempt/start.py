"""Internal handler: attempt_start — canonical orchestration entry."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.attempt.workflows import attempt_start_impl
from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_internal_sio, get_pool, get_redis_client
from app.infra.stream.socket_bridge import wrap_emit_with_stream_bridge
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit

internal_sio = get_internal_sio()


class AttemptStartInternalResult(BaseModel):
    """Structured result for the shared attempt start orchestration."""

    attempt_id: str
    chat_entry_id: str | None = None
    attempt_chat_id: str | None = None


async def attempt_start_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> AttemptStartInternalResult:
    """Run canonical attempt start orchestration for any surface."""
    from app.infra.attempt.proceed import attempt_proceed_internal_impl

    sid = data.get("sid", "")

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for attempt_start")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for attempt_start")

    async def _run(*, call_id: UUID | None = None) -> AttemptStartInternalResult:
        pool = get_pool()
        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="attempt",
            operation="start",
            emit=emit or make_emit(),
            call_id=call_id,
        )
        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        await attempt_start_impl(
            data,
            emit=_emit,
            pool=pool,
            redis=get_redis_client(),
            profile_id=profile_id,
            session_id=session_id,
        )

        proceed_events = [
            event
            for event in recorded
            if event.bus == "internal" and event.event == "attempt_proceed"
        ]
        created_attempt_id = (
            proceed_events[0].data.get("attempt_id", "") if proceed_events else ""
        )
        for event in proceed_events:
            await attempt_proceed_internal_impl(
                {
                    **event.data,
                    "profile_id": profile_id,
                    "session_id": session_id,
                },
                emit=_emit,
            )

        for event in recorded:
            if event.bus != "internal":
                continue
            if event.event == "attempt_started":
                return AttemptStartInternalResult(
                    attempt_id=event.data.get("attempt_id", ""),
                    chat_entry_id=event.data.get("chat_entry_id"),
                )
            if event.event == "attempt_chat_started":
                return AttemptStartInternalResult(
                    attempt_id=event.data.get("attempt_id", ""),
                    attempt_chat_id=event.data.get("chat_id"),
                )
            if event.event == "attempt_error":
                raise ValueError(event.data.get("message", "Failed to start attempt"))

        if created_attempt_id:
            return AttemptStartInternalResult(attempt_id=created_attempt_id)

        raise ValueError("Attempt start completed without a terminal start event")

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="attempt",
        profile_id=UUID(str(profile_id)),
        operation="start",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        response_model=AttemptStartInternalResult,
    )


@internal_sio.on("attempt_start")  # type: ignore
async def attempt_start_handler(data: dict[str, Any]) -> None:
    await attempt_start_internal_impl(data)
