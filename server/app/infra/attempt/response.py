"""Internal handler: attempt_response_submit — canonical orchestration entry."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_internal_sio, get_pool, get_redis_client
from app.infra.stream.socket_bridge import wrap_emit_with_stream_bridge
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit
from app.infra.attempt.client_types import AttemptResponsePayload
from app.infra.websocket.attempt_types import (
    AttemptErrorData,
    AttemptResponseResultData,
)

internal_sio = get_internal_sio()


class AttemptResponseInternalResult(BaseModel):
    success: bool
    message: str | None = None
    is_correct: bool | None = None
    response_id: str | None = None


async def attempt_response_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> AttemptResponseInternalResult:
    """Run canonical attempt response orchestration for any surface."""
    payload = AttemptResponsePayload(**data)

    sid = data.get("sid", "")
    chat_id = payload.chat_id
    question_id = payload.question_id
    option_ids = payload.option_ids

    profile_id = data.get("profile_id")
    if not profile_id:
        raise ValueError("Missing profile_id for attempt_response_submit")
    session_id = data.get("session_id")
    if not session_id:
        raise ValueError("Missing session_id for attempt_response_submit")

    async def _run() -> AttemptResponseInternalResult:
        from app.tools.entries.attempt_chat.search import search_attempt_chats
        from app.tools.entries.attempt_responses.create import (
            create_attempt_responses,
        )
        from app.tools.entries.attempt_responses.refresh import (
            refresh_attempt_responses,
        )
        from app.tools.entries.calls.create import create_call
        from app.tools.entries.groups.get import get_groups
        from app.tools.entries.runs.create import create_run

        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="attempt",
            operation="response",
            emit=emit or make_emit(),
            entity_id=None,
        )
        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        async with get_pool().acquire() as conn:
            attempt_chats, _ = await search_attempt_chats(
                conn,
                attempt_chat_ids=[chat_id],
                bypass_mv=True,
                limit=1,
            )
            if not attempt_chats:
                await _emit(
                    [
                        SocketEvent(
                            bus="internal",
                            event="attempt_error",
                            data=AttemptErrorData(
                                sid=sid,
                                error_type="quiz",
                                message="Attempt chat not found",
                                chat_id=str(chat_id),
                            ).model_dump(mode="json"),
                        )
                    ]
                )
            else:
                attempt_chat = attempt_chats[0]
                if not attempt_chat.group_id:
                    await _emit(
                        [
                            SocketEvent(
                                bus="internal",
                                event="attempt_error",
                                data=AttemptErrorData(
                                    sid=sid,
                                    error_type="quiz",
                                    message="Attempt chat group not found",
                                    chat_id=str(chat_id),
                                ).model_dump(mode="json"),
                            )
                        ]
                    )
                else:
                    groups = await get_groups(
                        conn,
                        ids=[attempt_chat.group_id],
                        bypass_mv=True,
                    )
                    if not groups:
                        await _emit(
                            [
                                SocketEvent(
                                    bus="internal",
                                    event="attempt_error",
                                    data=AttemptErrorData(
                                        sid=sid,
                                        error_type="quiz",
                                        message="Attempt chat session not found",
                                        chat_id=str(chat_id),
                                    ).model_dump(mode="json"),
                                )
                            ]
                        )
                    else:
                        group = groups[0]
                        try:
                            run = await create_run(
                                conn,
                                group_id=attempt_chat.group_id,
                                session_id=group.session_id,
                            )
                            call = await create_call(
                                conn,
                                run_id=run.id,
                                session_id=group.session_id,
                            )
                            response = await create_attempt_responses(
                                conn,
                                chat_id=chat_id,
                                call_id=call.id,
                                question_ids=[question_id],
                                option_ids=option_ids,
                            )
                            await refresh_attempt_responses(conn)
                        except asyncpg.ForeignKeyViolationError:
                            await _emit(
                                [
                                    SocketEvent(
                                        bus="internal",
                                        event="attempt_error",
                                        data=AttemptErrorData(
                                            sid=sid,
                                            error_type="quiz",
                                            message="Invalid question or option selection",
                                            chat_id=str(chat_id),
                                        ).model_dump(mode="json"),
                                    )
                                ]
                            )
                        else:
                            await _emit(
                                [
                                    SocketEvent(
                                        bus="internal",
                                        event="attempt_response_result",
                                        data=AttemptResponseResultData(
                                            sid=sid,
                                            success=True,
                                            message="Response submitted",
                                            is_correct=None,
                                            response_id=str(response.id),
                                        ).model_dump(mode="json"),
                                    )
                                ]
                            )

        for event in recorded:
            if event.bus != "internal":
                continue
            if event.event == "attempt_response_result":
                return AttemptResponseInternalResult(
                    success=bool(event.data.get("success", False)),
                    message=event.data.get("message"),
                    is_correct=event.data.get("is_correct"),
                    response_id=event.data.get("response_id"),
                )
            if event.event == "attempt_error":
                error = AttemptErrorData(**event.data)
                raise ValueError(error.message)

        raise ValueError("Attempt response completed without a terminal event")

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="attempt",
        profile_id=UUID(str(profile_id)),
        operation="response",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        entity_id=(
            UUID(str(data["attempt_id"])) if data.get("attempt_id") is not None else None
        ),
        response_model=AttemptResponseInternalResult,
    )


@internal_sio.on("attempt_response_submit")  # type: ignore
async def attempt_response_handler(data: dict[str, Any]) -> None:
    await attempt_response_internal_impl(data)
