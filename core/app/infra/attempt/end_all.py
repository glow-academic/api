"""Internal handler: attempt_end_all — mark all remaining chats as complete."""

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
    emit=None,
    audit: bool = True,
) -> AttemptEndAllInternalResult:
    """Mark all chats in an attempt as completed using chat_complete primitive."""
    from app.tools.entries.attempt_chat_bridge.search import (
        search_attempt_chat_bridges,
    )
    from app.tools.entries.attempt_chat_completion.create import (
        create_attempt_chat_completion,
    )
    from app.tools.entries.attempt.refresh import refresh_attempt
    from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
    from app.tools.entries.attempt_chat_completion.refresh import (
        refresh_attempt_chat_completion,
    )

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

    session_uuid = UUID(str(session_id))
    attempt_id = payload.attempt_id

    async def _run(*, call_id: UUID | None = None, **_kw) -> AttemptEndAllInternalResult:
        pool = get_pool()

        async with pool.acquire() as conn:
            bridges = await search_attempt_chat_bridges(
                conn,
                attempt_ids=[attempt_id],
                limit=1000,
                bypass_mv=True,
            )

            for bridge in bridges:
                if bridge.attempt_chat_id:
                    await create_attempt_chat_completion(
                        conn,
                        chat_id=bridge.attempt_chat_id,
                        session_id=session_uuid,
                    )

            await refresh_attempt_chat_completion(conn)
            await refresh_attempt_chat(conn)
            await refresh_attempt(conn)

        return AttemptEndAllInternalResult(
            attempt_id=str(attempt_id),
            success=True,
            all_scenarios_complete=True,
            message="All scenarios completed",
        )

    if not audit:
        return await _run()

    identity = await resolve_profile_identity_context(
        get_pool(),
        UUID(str(profile_id)),
        get_redis_client(),
        session_id=session_uuid,
        attempt_id=attempt_id,
    )
    group_id = identity.group_id if identity else None

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="attempt",
        profile_id=UUID(str(profile_id)),
        operation="end_all",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=session_uuid,
        attempt_id=attempt_id,
        group_id=group_id,
        sid=sid,
        rooms=[sid] if sid else None,
        response_model=AttemptEndAllInternalResult,
    )


@internal_sio.on("attempt_end_all")  # type: ignore
async def attempt_end_all_handler(data: dict[str, Any]) -> None:
    await attempt_end_all_internal_impl(data)
