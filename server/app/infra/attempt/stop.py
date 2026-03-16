"""Internal handler: attempt_stop_message — canonical orchestration entry."""

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
from app.infra.websocket.cancel_active_result import cancel_active_result
from app.infra.websocket.cancel_active_run import cancel_active_run
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit
from app.infra.attempt.client_types import AttemptStopPayload
from app.infra.websocket.attempt_types import AttemptStoppedData
from app.tools.entries.attempt_chat.get import get_attempt_chats
from app.tools.entries.attempt_message.search import search_attempt_messages
from app.tools.entries.attempt_message_completion.create import (
    create_attempt_message_completion,
)
from app.tools.entries.calls.create import create_call
from app.tools.entries.runs.create import create_run

internal_sio = get_internal_sio()


class AttemptStopInternalResult(BaseModel):
    chat_id: str
    success: bool
    message: str | None = None


async def attempt_stop_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> AttemptStopInternalResult:
    """Run canonical attempt stop orchestration for any surface."""
    sid = data.get("sid", "")
    payload = AttemptStopPayload(**data)

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for attempt_stop_message")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for attempt_stop_message")

    async def _run() -> AttemptStopInternalResult:
        chat_id = str(payload.chat_id)
        profile_id_uuid = UUID(profile_id)
        session_id_uuid = UUID(session_id)

        await cancel_active_result(chat_id)
        await cancel_active_run(chat_id)

        pool = get_pool()
        redis = get_redis_client()
        async with pool.acquire() as conn:
            chat_entries = await get_attempt_chats(conn, [payload.chat_id])
            if not chat_entries or not chat_entries[0].group_id:
                raise ValueError(f"Group not found for chat {chat_id}")
            group_id = chat_entries[0].group_id

            identity = await resolve_profile_identity_context(
                pool,
                profile_id_uuid,
                redis,
                session_id=session_id_uuid,
            )
            profiles_id = identity.profiles_id if identity else None

            messages, _ = await search_attempt_messages(
                conn,
                chat_ids=[payload.chat_id],
                limit=1,
                bypass_mv=True,
            )

            if not messages:
                result = AttemptStopInternalResult(
                    chat_id=chat_id,
                    success=False,
                    message="No active message found for this chat",
                )
            else:
                latest_message = messages[0]
                run = await create_run(
                    conn,
                    group_id=group_id,
                    session_id=session_id_uuid,
                    profiles_id=profiles_id,
                )
                call = await create_call(
                    conn,
                    run_id=run.id,
                    session_id=session_id_uuid,
                )
                await create_attempt_message_completion(
                    conn,
                    attempt_message_id=latest_message.message_id,
                    call_id=call.id,
                    stop=True,
                )
                result = AttemptStopInternalResult(chat_id=chat_id, success=True)

        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="attempt",
            operation="stop",
            emit=emit or make_emit(),
            entity_id=payload.chat_id,
        )
        await downstream_emit(
            [
                SocketEvent(
                    bus="internal",
                    event="attempt_stopped",
                    data=AttemptStoppedData(
                        sid=sid,
                        rooms=[sid, f"attempt_{chat_id}"] if sid else None,
                        chat_id=chat_id,
                        success=result.success,
                        message=result.message,
                    ).model_dump(mode="json"),
                )
            ]
        )
        return result

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="attempt",
        profile_id=UUID(str(profile_id)),
        operation="stop",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        entity_id=payload.chat_id,
        response_model=AttemptStopInternalResult,
    )


@internal_sio.on("attempt_stop_message")  # type: ignore
async def attempt_stop_handler(data: dict[str, Any]) -> None:
    await attempt_stop_internal_impl(data)
