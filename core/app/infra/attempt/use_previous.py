"""Internal handler: attempt_use_previous — bridge previous chats into current attempt."""

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
from app.infra.attempt.client_types import AttemptUsePreviousPayload
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.attempt_chat_completion.create import (
    create_attempt_chat_completion,
)
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


class AttemptUsePreviousInternalResult(BaseModel):
    success: bool
    message: str | None = None
    attempt_id: str | None = None


async def attempt_use_previous_internal_impl(
    data: dict[str, Any],
    *,
    emit=None,
    audit: bool = True,
) -> AttemptUsePreviousInternalResult:
    """Bridge previous attempt chats into current attempt and mark them complete."""
    from app.tools.entries.attempt.refresh import refresh_attempt
    from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
    from app.tools.entries.attempt_chat_completion.refresh import (
        refresh_attempt_chat_completion,
    )

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

    session_uuid = UUID(str(session_id))
    pool = get_pool()

    async with pool.acquire() as conn:
        for (
            _chat_entry_id_str,
            attempt_chat_id_str,
        ) in payload.previous_chat_map.items():
            if not attempt_chat_id_str:
                continue
            attempt_chat_id = UUID(attempt_chat_id_str)
            try:
                await create_attempt_chat_bridge(
                    conn,
                    attempt_id=payload.attempt_id,
                    attempt_chat_id=attempt_chat_id,
                    session_id=session_uuid,
                )
                # Mark the bridged chat as complete (idempotent)
                await create_attempt_chat_completion(
                    conn,
                    chat_id=attempt_chat_id,
                    session_id=session_uuid,
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to bridge attempt_chat {attempt_chat_id_str}: {exc}"
                )

        await refresh_attempt_chat_completion(conn)
        await refresh_attempt_chat(conn)
        await refresh_attempt(conn)

    return AttemptUsePreviousInternalResult(
        success=True,
        attempt_id=str(payload.attempt_id),
    )


@internal_sio.on("attempt_use_previous")  # type: ignore
async def attempt_use_previous_handler(data: dict[str, Any]) -> None:
    await attempt_use_previous_internal_impl(data)
