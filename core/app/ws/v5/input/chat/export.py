"""Input: chat.export"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.chat.export import export_chat_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.profile_identity_context import resolve_profile_identity_context

internal_sio = get_internal_sio()


class ChatExportPayload(BaseModel):
    """Payload for chat.export socket event."""

    chat_entry_id: UUID
    attempt_id: UUID | None = Field(None)
    draft_id: UUID | None = Field(None)


@sio.on("chat.export")  # type: ignore
async def chat_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ChatExportPayload(**data)
    except Exception as e:
        await internal_sio.emit("chat.export.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    async def _runner():
        profile_ctx = await resolve_profile_identity_context(
            pool,
            identity.profile_id,
            redis,
            session_id=identity.session_id,
            draft_id=payload.draft_id,
            attempt_id=payload.attempt_id,
        )
        group_id = profile_ctx.group_id if profile_ctx else None
        if group_id is None:
            raise ValueError("Group ID could not be resolved for chat export")

        return await export_chat_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            chat_entry_id=payload.chat_entry_id,
            group_id=group_id,
            attempt_id=payload.attempt_id,
            draft_id=payload.draft_id,
        )

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="chat",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=_runner,
        arguments=payload.model_dump(mode="json"),
    )
