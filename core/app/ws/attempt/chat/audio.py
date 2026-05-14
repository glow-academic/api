"""Input: attempt.chat_audio — attach audio to a persisted chat message."""

from typing import Any
from uuid import UUID

from app.infra.attempt.chat_audio import attempt_chat_audio_internal_impl
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity


@sio.on("attempt.chat_audio")  # type: ignore
async def attempt_chat_audio(sid: str, data: dict[str, Any]) -> dict[str, Any]:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return {"error": "Missing socket identity"}

    message_id = data.get("message_id")
    audios_id = data.get("audios_id")
    if not message_id or not audios_id:
        return {"error": "message_id and audios_id are required"}

    pool = get_pool()
    redis = get_redis_client()

    try:
        result = await attempt_chat_audio_internal_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            message_id=UUID(str(message_id)),
            audios_id=UUID(str(audios_id)),
        )
    except Exception as exc:
        return {"error": str(exc)}

    return result.model_dump(mode="json")
