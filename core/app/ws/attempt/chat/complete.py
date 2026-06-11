"""Input: attempt.chat_complete — canonical WS handler.

Mirrors the HTTP ``POST /attempt/chat_complete`` route: marks an attempt
chat as completed through the audit framework so
``attempt.chat_complete.completed`` (the event the client's WS command
channel awaits) flows back over Socket.IO. Without this handler the
client-emitted ``attempt.chat_complete`` event had no ``sio.on`` listener,
so python-socketio sent no ack and the client hung for the full 30s
command timeout.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.attempt.chat_complete import chat_complete_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder, sio
from app.infra.identity.socket import resolve_socket_identity


class ChatCompletePayload(BaseModel):
    chat_id: UUID
    message: str = ""
    idempotency_key: UUID | None = None
    soft: bool = False
    accept: bool | None = None


@sio.on("attempt.chat_complete")  # type: ignore
async def attempt_chat_complete(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ChatCompletePayload(**data)
    except Exception:
        return

    pool = get_pool()
    redis = get_redis_client()

    async def _runner(call_id: UUID | None = None) -> dict[str, Any]:
        result = await chat_complete_attempt_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            chat_id=payload.chat_id,
            message=payload.message,
            soft=payload.soft,
            accept=payload.accept,
            idempotency_key=payload.idempotency_key,
            call_id=call_id,
        )
        return {
            "success": True,
            "completion_id": result["completion_id"],
            "chat_id": result["chat_id"],
            "idempotency_key": result.get("idempotency_key"),
        }

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="chat_complete",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=_runner,
        arguments=payload.model_dump(mode="json"),
        operation_key=payload.idempotency_key,
        upload_folder=get_upload_folder(),
    )
