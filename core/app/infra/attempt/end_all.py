"""Internal handler: attempt_end_all — canonical orchestration entry."""

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
from app.infra.stream.socket_bridge import wrap_emit_with_stream_bridge
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit
from app.infra.attempt.client_types import AttemptEndAllPayload

internal_sio = get_internal_sio()


class AttemptEndAllInternalResult(BaseModel):
    attempt_id: str
    success: bool
    all_scenarios_complete: bool = False
    message: str | None = None


async def attempt_end_all_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> AttemptEndAllInternalResult:
    """Run canonical attempt end-all orchestration for any surface."""
    from app.infra.attempt.proceed import attempt_proceed_internal_impl

    sid = data.get("sid", "")
    payload = AttemptEndAllPayload(**data)

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for attempt_end_all")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for attempt_end_all")

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

    async def _run(*, call_id: UUID | None = None) -> AttemptEndAllInternalResult:
        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="attempt",
            operation="end_all",
            emit=emit or make_emit(),
            call_id=call_id,
        )
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
                "complete_all": True,
            },
            emit=_emit,
            audit=False,
        )

        for event in recorded:
            if event.bus != "internal":
                continue
            if event.event == "attempt_ended":
                return AttemptEndAllInternalResult(
                    attempt_id=event.data.get("attempt_id", ""),
                    success=bool(event.data.get("success", False)),
                    all_scenarios_complete=bool(
                        event.data.get("all_scenarios_complete", False)
                    ),
                    message=event.data.get("message"),
                )
            if event.event == "attempt_error":
                raise ValueError(event.data.get("message", "Failed to end attempt"))

        raise ValueError("Attempt end-all completed without a terminal event")

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="attempt",
        profile_id=UUID(str(profile_id)),
        operation="end_all",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        attempt_id=payload.attempt_id,
        group_id=group_id,
        response_model=AttemptEndAllInternalResult,
    )


@internal_sio.on("attempt_end_all")  # type: ignore
async def attempt_end_all_handler(data: dict[str, Any]) -> None:
    await attempt_end_all_internal_impl(data)
