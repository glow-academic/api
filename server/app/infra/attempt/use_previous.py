"""Internal handler: attempt_use_previous — canonical orchestration entry."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_internal_sio, get_pool, get_redis_client
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit
from app.infra.attempt.client_types import AttemptUsePreviousPayload
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


class AttemptUsePreviousInternalResult(BaseModel):
    success: bool
    message: str | None = None
    attempt_id: str | None = None
    chat_id: str | None = None


async def attempt_use_previous_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> AttemptUsePreviousInternalResult:
    """Run canonical attempt use-previous orchestration for any surface."""
    from app.infra.attempt.proceed import attempt_proceed_internal_impl

    sid = data.get("sid", "")
    payload = AttemptUsePreviousPayload(**data)

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for attempt_use_previous")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for attempt_use_previous")

    identity = await resolve_profile_identity_context(
        get_pool(),
        UUID(profile_id),
        get_redis_client(),
        session_id=UUID(session_id),
        attempt_id=payload.attempt_id,
    )
    group_id = identity.group_id if identity else None
    if group_id is None:
        raise ValueError(f"Group not found for attempt {payload.attempt_id}")

    pool = get_pool()
    async with pool.acquire() as conn:
        for (
            _chat_entry_id_str,
            attempt_chat_id_str,
        ) in payload.previous_chat_map.items():
            if not attempt_chat_id_str:
                continue
            try:
                await create_attempt_chat_bridge(
                    conn,
                    attempt_id=payload.attempt_id,
                    attempt_chat_id=UUID(attempt_chat_id_str),
                    session_id=UUID(session_id),
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to bridge attempt_chat {attempt_chat_id_str}: {exc}"
                )

    async def _run() -> AttemptUsePreviousInternalResult:
        downstream_emit = emit or make_emit()
        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        await attempt_proceed_internal_impl(
            {
                "sid": sid,
                "profile_id": profile_id,
                "session_id": session_id,
                "attempt_id": str(payload.attempt_id),
                "group_id": str(group_id),
                "force_proceed": False,
            },
            emit=_emit,
            audit=False,
        )

        for event in recorded:
            if event.bus != "internal":
                continue
            if event.event == "attempt_started":
                return AttemptUsePreviousInternalResult(
                    success=True,
                    attempt_id=event.data.get("attempt_id"),
                    chat_id=event.data.get("chat_entry_id"),
                )
            if event.event == "attempt_chat_started":
                return AttemptUsePreviousInternalResult(
                    success=True,
                    attempt_id=event.data.get("attempt_id"),
                    chat_id=event.data.get("chat_id"),
                )
            if event.event == "attempt_ended":
                return AttemptUsePreviousInternalResult(
                    success=True,
                    attempt_id=event.data.get("attempt_id"),
                    message=event.data.get("message"),
                )
            if event.event == "attempt_error":
                raise ValueError(
                    event.data.get("message", "Failed to use previous attempt data")
                )

        return AttemptUsePreviousInternalResult(
            success=True,
            attempt_id=str(payload.attempt_id),
        )

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="attempt",
        profile_id=UUID(str(profile_id)),
        operation="use_previous",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        attempt_id=payload.attempt_id,
        group_id=group_id,
        response_model=AttemptUsePreviousInternalResult,
    )


@internal_sio.on("attempt_use_previous")  # type: ignore
async def attempt_use_previous_handler(data: dict[str, Any]) -> None:
    await attempt_use_previous_internal_impl(data)
