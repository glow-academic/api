"""Internal impl for attempt_audio_start — shared by WebSocket and HTTP.

Resolves group_id + attempt_id from attempt_chat_entry, creates run/call/conversation,
and emits to the generate pipeline with modality=audio.
"""

import uuid
from typing import Any

from pydantic import BaseModel

from app.infra.attempt.client_types import AttemptAudioStartPayload
from app.infra.globals import get_internal_sio, get_pool, get_redis_client
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.websocket.attempt_types import (
    GenerateRequestData,
)
from app.tools.entries.attempt_chat.get import get_attempt_chats
from app.tools.entries.attempt_conversations.create import (
    create_attempt_conversations,
)
from app.tools.entries.calls.create import create_call
from app.tools.entries.runs.create import create_run
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


class AudioStartInternalResult(BaseModel):
    """Structured result for audio start orchestration."""

    chat_id: str
    run_id: str
    group_id: str
    attempt_id: str


async def attempt_audio_start_internal_impl(
    data: dict[str, Any],
) -> AudioStartInternalResult:
    """Run canonical audio start orchestration for any surface.

    Required data keys: chat_id, profile_id, session_id.
    Optional: sid (empty string for HTTP callers).
    """
    payload = AttemptAudioStartPayload(**data)
    chat_id = payload.chat_id
    sid = data.get("sid", "")

    profile_id_str = data.get("profile_id")
    if not profile_id_str:
        raise ValueError("Missing profile_id for attempt_audio_start")

    session_id_str = data.get("session_id")
    if not session_id_str:
        raise ValueError("Missing session_id for attempt_audio_start")

    profile_id = uuid.UUID(str(profile_id_str))
    session_id = uuid.UUID(str(session_id_str))

    pool = get_pool()
    internal_sio = get_internal_sio()

    identity = await resolve_profile_identity_context(
        pool, profile_id, get_redis_client(), session_id=session_id
    )
    profiles_id = identity.profiles_id if identity else None

    async with pool.acquire() as conn:
        # Step 1: Resolve group_id + attempt_id from attempt_chat_entry
        chat_entries = await get_attempt_chats(conn, [chat_id])

        if not chat_entries or not chat_entries[0].group_id:
            raise ValueError(f"No group found for chat {chat_id}")

        group_id = chat_entries[0].group_id
        attempt_id = chat_entries[0].attempt_id

        # Step 2: Create run + call + conversation
        run = await create_run(
            conn,
            group_id=group_id,
            session_id=session_id,
            profiles_id=profiles_id,
        )
        call = await create_call(conn, run_id=run.id, session_id=session_id)
        conversation = await create_attempt_conversations(
            conn,
            chat_id=chat_id,
            call_id=call.id,
            run_id=run.id,
        )

    # Step 3: Emit to generate pipeline with modality=audio
    resource_types = ["contents", "hints"]

    await internal_sio.emit(
        "generate",
        GenerateRequestData(
            sid=sid,
            profile_id=str(profile_id),
            artifact_types=[{"name": "attempt", "operation": "get"}],
            artifact_id=str(attempt_id),
            resource_types=resource_types,
            save=True,
            run_id=str(run.id),
            group_id=str(group_id),
            modality="audio",
            metadata={
                "attempt_id": str(attempt_id),
                "chat_id": str(chat_id),
                "conversation_id": str(conversation.id),
            },
        ).model_dump(mode="json"),
    )

    return AudioStartInternalResult(
        chat_id=str(chat_id),
        run_id=str(run.id),
        group_id=str(group_id),
        attempt_id=str(attempt_id),
    )
