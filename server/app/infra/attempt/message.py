"""Internal handler: attempt_message — canonical orchestration entry."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.attempt.workflows import attempt_message_impl
from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_internal_sio, get_pool, get_redis_client
from app.infra.stream.socket_bridge import wrap_emit_with_stream_bridge
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit
from app.infra.attempt.client_types import AttemptMessagePayload

internal_sio = get_internal_sio()


class AttemptMessageInternalResult(BaseModel):
    chat_id: str
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    assistant_content: str | None = None


async def attempt_message_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> AttemptMessageInternalResult:
    """Run canonical attempt message orchestration for any surface."""
    payload = AttemptMessagePayload(**data)

    sid = data.get("sid", "")
    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for attempt_message")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for attempt_message")

    async def _run() -> AttemptMessageInternalResult:
        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="attempt",
            operation="message",
            emit=emit or make_emit(),
            entity_id=payload.chat_id,
        )
        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        await attempt_message_impl(
            {
                **data,
                "chat_id": str(payload.chat_id),
                "attempt_id": str(payload.attempt_id),
            },
            emit=_emit,
            pool=get_pool(),
            redis=get_redis_client(),
            profile_id=str(profile_id),
            session_id=str(session_id),
        )

        result = AttemptMessageInternalResult(chat_id=str(payload.chat_id))
        for event in recorded:
            if event.bus != "internal":
                continue
            if event.event == "attempt_user_complete":
                result.user_message_id = event.data.get("message_id")
            elif event.event == "attempt_assistant_start":
                result.assistant_message_id = event.data.get("message_id")
            elif event.event == "attempt_assistant_complete":
                result.assistant_message_id = (
                    event.data.get("message_id") or result.assistant_message_id
                )
                result.assistant_content = event.data.get("content")
            elif event.event == "attempt_error":
                raise ValueError(
                    event.data.get("message", "Failed to send attempt message")
                )

        if result.user_message_id or result.assistant_message_id:
            return result

        raise ValueError("Attempt message completed without a terminal event")

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="attempt",
        profile_id=UUID(str(profile_id)),
        operation="message",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        entity_id=payload.chat_id,
        attempt_id=payload.attempt_id,
        response_model=AttemptMessageInternalResult,
    )


@internal_sio.on("attempt_message")  # type: ignore
async def attempt_message_handler(data: dict[str, Any]) -> None:
    await attempt_message_internal_impl(data)
