"""Input: chat.export"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.attempt.chat.export import export_chat_impl
from app.infra.attempt.group import group_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


class ChatExportPayload(BaseModel):
    """Payload for chat.export socket event."""

    chat_entry_id: UUID
    attempt_id: UUID | None = Field(None)
    draft_id: UUID | None = Field(None)


@sio.on("attempt.chat_export")  # type: ignore
async def attempt_chat_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ChatExportPayload(**data)
    except Exception as e:
        await internal_sio.emit("attempt.chat_export.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    async def _runner():
        group_result = await group_attempt_impl(
            pool, redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            include_history=False,
        )
        return await export_chat_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            chat_entry_id=payload.chat_entry_id,
            group_id=group_result.group_id,
            attempt_id=payload.attempt_id,
            draft_id=payload.draft_id,
            session_id=identity.session_id,
        )

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="chat_export",
        profile_id=identity.profile_id,
        sid=sid,
        runner=_runner,
        arguments=payload.model_dump(mode="json"),
    )
