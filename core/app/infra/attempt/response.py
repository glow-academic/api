"""Internal handler: attempt_response_submit — canonical orchestration entry."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from app.infra.activate.activate import activate_rows
from app.infra.attempt.client_types import AttemptResponsePayload
from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_internal_sio, get_pool, get_redis_client
from app.infra.server_timing import timed
from app.infra.websocket.attempt_types import (
    AttemptErrorData,
    AttemptResponseResultData,
)
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call

internal_sio = get_internal_sio()

ARTIFACT = "attempt"
OPERATION = "chat_response"


class AttemptResponseInternalResult(BaseModel):
    success: bool
    message: str | None = None
    is_correct: bool | None = None
    response_id: str | None = None
    idempotency_key: str | None = None


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

    soft = bool(data.get("soft", False))
    accept = data.get("accept")
    idempotency_key = data.get("idempotency_key")
    if isinstance(idempotency_key, str):
        idempotency_key = UUID(idempotency_key)
    is_ack = accept is not None and idempotency_key is not None

    async def _run(call_id: UUID | None = None) -> AttemptResponseInternalResult:
        from app.infra.attempt.refresh import refresh_attempt_impl
        from app.tools.entries.attempt_chat.search import search_attempt_chats
        from app.tools.entries.attempt_responses.create import (
            create_attempt_responses,
        )

        redis = get_redis_client()

        # ── Short-circuit: ack — activate / reject the staged response ──
        if accept is not None and idempotency_key is not None:
            async with get_pool().acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != OPERATION:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="No pending response for this call.")
            response_id = (entry.patch or {}).get("response_id")
            if accept and response_id:
                async with get_pool().acquire() as conn:
                    await activate_rows(conn, table="attempt_responses_entry", ids=[UUID(response_id)])
                await refresh_attempt_impl(
                    get_pool(), redis, profile_id=UUID(str(profile_id)),
                    session_id=UUID(str(session_id)), targets=["attempt_responses_mv"],
                )
            async with get_pool().acquire() as conn:
                await create_soft_call(
                    conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                    operation=OPERATION, artifact_id=entry.artifact_id,
                    status="accepted" if accept else "rejected",
                )
            return AttemptResponseInternalResult(
                success=True, message="Response activated" if accept else "Response rejected",
                response_id=str(response_id or ""), idempotency_key=str(idempotency_key),
            )

        # Authorization (was MISSING — keyed solely by the caller-supplied
        # chat_id, this forges/corrupts the resolved chat owner's quiz/video
        # answer record + grade inputs. The chat below was only existence-checked
        # (search_attempt_chats), never owner-resolved. Resolve chat → owner and
        # enforce the shared attempt-mutation gate. Mirrors
        # chat_complete_attempt_impl.)
        from app.infra.attempt.permissions import enforce_attempt_access_by_chat
        from app.infra.profile_identity_context import (
            resolve_profile_identity_context,
        )

        requester = await resolve_profile_identity_context(
            get_pool(), UUID(str(profile_id)), redis,
        )
        await enforce_attempt_access_by_chat(
            get_pool(), redis, chat_id=chat_id, requester=requester,
        )

        downstream_emit = emit or make_emit()
        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        with timed("db_write"):
         async with get_pool().acquire() as conn:
            attempt_chats, _ = await search_attempt_chats(
                conn, redis,
                attempt_chat_ids=[chat_id],
                limit=1,
            )
            if not attempt_chats:
                await _emit(
                    [
                        SocketEvent(
                            bus="internal",
                            event="attempt.quiz.error",
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
                try:
                    response = await create_attempt_responses(
                        conn, redis,
                        chat_id=chat_id,
                        session_id=UUID(str(session_id)),
                        question_ids=[question_id],
                        option_ids=option_ids,
                        soft=soft,
                    )
                    if soft and call_id is not None:
                        await create_soft_call(
                            conn, redis, call_id=call_id, artifact=ARTIFACT,
                            operation=OPERATION, artifact_id=response.id, status="pending",
                            patch={"response_id": str(response.id)},
                        )
                    if not soft:
                        await refresh_attempt_impl(
                            get_pool(), redis,
                            profile_id=UUID(str(profile_id)),
                            session_id=UUID(str(session_id)),
                            targets=["attempt_responses_mv"],
                        )
                except asyncpg.ForeignKeyViolationError:
                    await _emit(
                        [
                            SocketEvent(
                                bus="internal",
                                event="attempt.quiz.error",
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
                    idempotency_key=str(call_id) if call_id else None,
                )
            if event.event == "attempt_error":
                error = AttemptErrorData(**event.data)
                raise ValueError(error.message)

        raise ValueError("Attempt response completed without a terminal event")

    if not audit:
        return await _run()

    sid = data.get("sid", "")
    # Resolve the time-windowed group so the wrapper mints a calls_entry
    # (``can_audit`` needs group_id) + threads its call_id (the soft key).
    from app.infra.attempt.group import group_attempt_impl
    group_result = await group_attempt_impl(
        get_pool(), get_redis_client(),
        profile_id=UUID(str(profile_id)), session_id=UUID(str(session_id)), id_only=True,
    )
    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact=ARTIFACT,
        profile_id=UUID(str(profile_id)),
        group_id=group_result.group_id,
        operation=OPERATION,
        runner=_run,
        arguments={"accept": accept} if is_ack else build_audit_arguments(data),
        operation_key=idempotency_key,  # idempotency replay gate
        session_id=UUID(str(session_id)),
        entity_id=(
            UUID(str(data["attempt_id"])) if data.get("attempt_id") is not None else None
        ),
        sid=sid,
        response_model=AttemptResponseInternalResult,
    )


@internal_sio.on("attempt_response_submit")  # type: ignore
async def attempt_response_handler(data: dict[str, Any]) -> None:
    await attempt_response_internal_impl(data)
