"""Internal handler: attempt_next — canonical orchestration entry."""

from typing import Any
from uuid import UUID

from app.infra.attempt.workflows import attempt_next_impl
from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_internal_sio, get_pool, get_redis_client
from app.infra.stream.socket_bridge import wrap_emit_with_stream_bridge
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit
from app.infra.attempt.client_types import AttemptNextPayload
from app.infra.attempt.start import AttemptStartInternalResult
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


async def attempt_next_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> AttemptStartInternalResult:
    """Run canonical attempt next orchestration for any surface."""
    from app.infra.attempt.proceed import attempt_proceed_internal_impl

    sid = data.get("sid", "")
    try:
        payload = AttemptNextPayload(**data)
    except Exception as e:
        raise ValueError(f"Invalid attempt_next payload: {e}") from e

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for attempt_next")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for attempt_next")

    async def _run(*, call_id: UUID | None = None) -> AttemptStartInternalResult:
        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="attempt",
            operation="next",
            emit=emit or make_emit(),
            call_id=call_id,
        )
        recorded: list[SocketEvent] = []
        workflow_sid = sid or f"http-attempt-next:{session_id}"

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        await attempt_next_impl(
            {
                **data,
                "sid": workflow_sid,
            },
            emit=_emit,
            attempt_id=str(payload.attempt_id),
            draft_id=str(payload.draft_id) if payload.draft_id else None,
            profile_id=profile_id,
            session_id=session_id,
            pool=get_pool(),
            redis=get_redis_client(),
        )

        proceed_events = [
            event
            for event in recorded
            if event.bus == "internal" and event.event == "attempt_proceed"
        ]
        proceeded_attempt_id = (
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
            if event.event == "attempt_ended":
                return AttemptStartInternalResult(
                    attempt_id=event.data.get("attempt_id", ""),
                )
            if event.event == "attempt_error":
                raise ValueError(
                    event.data.get("message", "Failed to continue attempt")
                )

        if proceeded_attempt_id:
            return AttemptStartInternalResult(attempt_id=proceeded_attempt_id)

        raise ValueError("Attempt next completed without a terminal event")

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="attempt",
        profile_id=UUID(str(profile_id)),
        operation="next",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        attempt_id=payload.attempt_id,
        draft_id=payload.draft_id,
        response_model=AttemptStartInternalResult,
    )


@internal_sio.on("attempt_next")  # type: ignore
async def attempt_next_handler(data: dict[str, Any]) -> None:
    await attempt_next_internal_impl(data)
