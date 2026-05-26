"""Attempt chat_audio — attach an audio asset to a chat message.

Post-hoc attachment: the message is already created (via
``/attempt/chat/message``), and this endpoint records the audio-message
link in ``attempt_audio_entry``. Mirrors the attempt_hint pattern.

The realtime adapter calls this server-internally for assistant turns:
the model's ``Attempt_Chat_Message`` tool call returns a ``message_id``
and the adapter's assistant audio capture yields an ``audios_id``; both
flow through here so clients only see fully-linked messages via the MV.

Soft/accept (stage-inactive): ``soft=True`` writes the link row dormant
(``active=False``) + a pending ``soft_calls_entry``; the ack activates it or rejects.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.attempt_audio.create import create_attempt_audio
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.utils.cache.invalidate_tags import invalidate_tags

ARTIFACT = "attempt"
OPERATION = "chat_audio"


class AttemptChatAudioInternalResult(BaseModel):
    success: bool
    attempt_audio_id: str
    idempotency_key: str | None = None


async def attempt_chat_audio_internal_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    message_id: UUID | None = None,
    audios_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
) -> AttemptChatAudioInternalResult:
    """Create an ``attempt_audio_entry`` row linking ``message_id`` to
    ``audios_id`` (with soft/accept). Returns the new entry's id.
    """
    # ── Short-circuit: ack — activate / reject the staged link ──
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(status_code=404, detail="No pending chat audio for this call.")
        audio_id = (entry.patch or {}).get("attempt_audio_id")
        if accept and audio_id:
            async with pool.acquire() as conn:
                await activate_rows(conn, table="attempt_audio_entry", ids=[UUID(audio_id)])
            await invalidate_tags(["entries", "attempt", "attempt_audio"], redis=redis)
        async with pool.acquire() as conn:
            await create_soft_call(
                conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                operation=OPERATION, artifact_id=entry.artifact_id,
                status="accepted" if accept else "rejected",
            )
        return AttemptChatAudioInternalResult(
            success=True, attempt_audio_id=str(audio_id or ""),
            idempotency_key=str(idempotency_key),
        )

    if message_id is None or audios_id is None:
        raise HTTPException(status_code=400, detail="message_id and audios_id are required.")

    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id,
        )
    if profile is None:
        raise HTTPException(
            status_code=401, detail="Profile not found. Please sign in again.",
        )

    effective_session_id = session_id or profile.session_id
    if effective_session_id is None:
        raise HTTPException(
            status_code=400, detail="session_id is required for attempt_chat_audio.",
        )

    with timed("db_write"):
     async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_attempt_audio(
                conn,
                redis, message_id=message_id,
                audios_id=audios_id,
                session_id=effective_session_id,
                soft=soft,
            )
            if soft and call_id is not None:
                await create_soft_call(
                    conn, redis, call_id=call_id, artifact=ARTIFACT,
                    operation=OPERATION, artifact_id=result.id, status="pending",
                    patch={"attempt_audio_id": str(result.id)},
                )

    if not soft:
        await invalidate_tags(["entries", "attempt", "attempt_audio"], redis=redis)

    return AttemptChatAudioInternalResult(
        success=True, attempt_audio_id=str(result.id),
        idempotency_key=str(call_id) if call_id else None,
    )
