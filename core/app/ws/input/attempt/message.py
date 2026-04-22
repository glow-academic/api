"""Input: attempt.chat.message — unified text and audio input.

Accepts text, audio (raw bytes), or audio_id (uploaded file reference).
Routes through voice pipeline when a voice session is active,
otherwise uses the standard text generation pipeline.
"""

from typing import Any

from app.infra.attempt.message import attempt_message_internal_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder, sio
from app.infra.group.resolve import resolve_group_impl
from app.infra.identity.socket import resolve_socket_identity
from app.infra.websocket.attempt.audio_frame import (
    attempt_audio_frame_internal_impl,
)
from app.infra.websocket.session_store import get_session_by_chat_id
from app.tools.entries.uploads.get import get_upload


@sio.on("attempt.chat.message")  # type: ignore
async def attempt_message(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    chat_id = data.get("chat_id")
    if not chat_id:
        return

    text = data.get("text") or data.get("message")
    audio = data.get("audio")  # raw bytes (legacy socket path)
    audio_id = data.get("audio_id")  # uploaded file reference

    # Resolve audio bytes from audio_id if provided
    audio_bytes: bytes | None = audio
    if audio_id and not audio_bytes:
        try:
            from pathlib import Path
            from uuid import UUID

            pool = get_pool()
            async with pool.acquire() as conn:
                upload = await get_upload(conn, UUID(str(audio_id)))
            if upload:
                file_path = get_upload_folder() / upload.file_path
                if file_path.exists():
                    audio_bytes = Path(file_path).read_bytes()
        except Exception:
            pass

    voice_session = get_session_by_chat_id(str(chat_id))

    # Voice session active: route through voice pipeline
    if voice_session:
        if audio_bytes:
            attempt_audio_frame_internal_impl(chat_id=str(chat_id), audio=audio_bytes)
            return
        if text:
            await voice_session.inbound_queue.put({"type": "text", "content": text})
            return

    # No voice session: standard text pipeline
    if not text:
        return

    pool = get_pool()
    redis = get_redis_client()

    # Resolve group so audit can fire proper lifecycle events
    # (without group_id the audit layer falls to its non-audit branch).
    group_resolve = await resolve_group_impl(
        pool,
        redis,
        artifact_type="attempt",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        include_history=False,
    )

    async def _runner() -> dict[str, Any]:
        result = await attempt_message_internal_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            chat_id=chat_id,
            text=text,
            message=text,
            attempt_id=data.get("attempt_id"),
            persona_id=data.get("persona_id"),
            contents=data.get("contents"),
            parent_message_id=data.get("parent_message_id"),
            auto_link_parent=data.get("auto_link_parent", True),
            sid=sid,
        )
        return result.model_dump(mode="json")

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="chat_message",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        group_id=group_resolve.group_id,
        sid=sid,
        rooms=[sid],
        runner=_runner,
        arguments={"chat_id": chat_id, "text": text, "persona_id": data.get("persona_id")},
    )
