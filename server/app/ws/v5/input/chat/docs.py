"""Input: chat.docs"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.chat.docs import docs_chat_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


class ChatDocsPayload(BaseModel):
    """Payload for chat.docs socket event."""

    entity_id: UUID | None = Field(None)


@sio.on("chat.docs")  # type: ignore
async def chat_docs(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ChatDocsPayload(**data)
    except Exception as e:
        await internal_sio.emit("chat.docs.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="chat",
        operation="docs",
        profile_id=identity.profile_id,
        entity_id=payload.entity_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: docs_chat_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            entity_id=payload.entity_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
