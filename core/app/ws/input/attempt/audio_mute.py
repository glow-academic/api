"""Input: attempt.audio_mute"""

import uuid as uuid_mod
from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.websocket.session_store import get_session_by_chat_id
from app.tools.entries.attempt_mutes.create import create_attempt_mutes
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


@sio.on("attempt.chat.mute")  # type: ignore
async def attempt_audio_mute(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    chat_id = data.get("chat_id")
    if not chat_id:
        return
    session = get_session_by_chat_id(chat_id)
    if not session:
        return

    muted = data.get("muted", False)

    async def _runner() -> dict[str, Any]:
        if session.conversation_id:
            try:
                pool = get_pool()
                async with pool.acquire() as conn:
                    await create_attempt_mutes(
                        conn,
                        conversation_id=uuid_mod.UUID(session.conversation_id),
                        call_id=uuid_mod.uuid4(),
                        muted=muted,
                    )
            except Exception as e:
                logger.warning(f"Failed to record mute event: {e}")

        await session.inbound_queue.put({"type": "mic.set_muted", "muted": muted})
        return {"chat_id": chat_id, "muted": muted, "success": True}

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="chat.mute",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=_runner,
        arguments={"chat_id": chat_id, "muted": muted},
    )
