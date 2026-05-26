"""Internal impl for attempt_chat_voice — shared by WebSocket and HTTP.

Canonical per generate redesign: opens a realtime conversation and returns
its id. No AI dispatch here — the client separately calls /attempt/generate
with the returned conversation_id.

Soft/accept (stage-inactive): ``soft=True`` writes the conversation row dormant
(``active=False``) + a pending ``soft_calls_entry``; the ack activates it or
rejects. The wrapper lives inside this impl, so ``operation_key`` is wired for
the replay gate, ``group_id`` is resolved (so ``can_audit`` holds), and the
wrapper's ``call_id`` is the soft key.
"""

import uuid
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from app.infra.activate.activate import activate_rows
from app.infra.attempt.client_types import AttemptAudioStartPayload
from app.infra.attempt.group import group_attempt_impl
from app.infra.events.audit import build_audit_arguments, run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client
from app.tools.entries.attempt_chat.get import get_attempt_chats
from app.tools.entries.attempt_conversations.create import (
    create_attempt_conversations,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

ARTIFACT = "attempt"
OPERATION = "chat_voice"


class AudioStartInternalResult(BaseModel):
    """Structured result for audio start orchestration."""

    chat_id: str
    attempt_id: str
    conversation_id: str
    group_id: str
    idempotency_key: str | None = None


async def attempt_chat_voice_internal_impl(
    data: dict[str, Any],
    *,
    audit: bool = True,
) -> AudioStartInternalResult:
    """Open a realtime conversation for a chat and return its id.

    Required data keys: chat_id, profile_id, session_id.

    This endpoint does NOT trigger AI generation. The client calls
    /attempt/generate with modalities + conversation_id separately.
    """
    redis = get_redis_client()
    payload = AttemptAudioStartPayload(**data)
    chat_id = payload.chat_id

    profile_id_str = data.get("profile_id")
    if not profile_id_str:
        raise ValueError("Missing profile_id for attempt_chat_voice")
    session_id_str = data.get("session_id")
    if not session_id_str:
        raise ValueError("Missing session_id for attempt_chat_voice")

    profile_id = uuid.UUID(str(profile_id_str))
    session_id = uuid.UUID(str(session_id_str))

    soft = bool(data.get("soft", False))
    accept = data.get("accept")
    idempotency_key = data.get("idempotency_key")
    if isinstance(idempotency_key, str):
        idempotency_key = uuid.UUID(idempotency_key)
    is_ack = accept is not None and idempotency_key is not None

    pool = get_pool()
    group_result = await group_attempt_impl(pool, redis, profile_id=profile_id, session_id=session_id)
    group_id = group_result.group_id

    async def _run(call_id: uuid.UUID | None = None) -> AudioStartInternalResult:
        # ── Short-circuit: ack — activate / reject the staged conversation ──
        if accept is not None and idempotency_key is not None:
            async with pool.acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != OPERATION:
                raise HTTPException(status_code=404, detail="No pending voice conversation for this call.")
            ids = entry.patch or {}
            conv_id = ids.get("conversation_id")
            if accept and conv_id:
                async with pool.acquire() as conn:
                    await activate_rows(conn, table="attempt_conversations_entry", ids=[uuid.UUID(conv_id)])
            async with pool.acquire() as conn:
                await create_soft_call(
                    conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                    operation=OPERATION, artifact_id=entry.artifact_id,
                    status="accepted" if accept else "rejected",
                )
            return AudioStartInternalResult(
                chat_id=str(chat_id),
                attempt_id=str(ids.get("attempt_id", "")),
                conversation_id=str(conv_id or ""),
                group_id=str(ids.get("group_id", group_id)),
                idempotency_key=str(idempotency_key),
            )

        async with pool.acquire() as conn:
            async with conn.transaction():
                chat_entries = await get_attempt_chats(conn, [chat_id], redis)
                if not chat_entries:
                    raise ValueError(f"Attempt chat {chat_id} not found")
                attempt_id = chat_entries[0].attempt_id
                conversation = await create_attempt_conversations(
                    conn, redis, chat_id=chat_id, session_id=session_id, soft=soft,
                )
                if soft and call_id is not None:
                    await create_soft_call(
                        conn, redis, call_id=call_id, artifact=ARTIFACT,
                        operation=OPERATION, artifact_id=conversation.id, status="pending",
                        patch={
                            "conversation_id": str(conversation.id),
                            "attempt_id": str(attempt_id),
                            "group_id": str(group_id),
                        },
                    )

        return AudioStartInternalResult(
            chat_id=str(chat_id),
            attempt_id=str(attempt_id),
            conversation_id=str(conversation.id),
            group_id=str(group_id),
            idempotency_key=str(call_id) if call_id else None,
        )

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact=ARTIFACT,
        profile_id=profile_id,
        group_id=group_id,
        operation=OPERATION,
        runner=_run,
        arguments={"accept": accept} if is_ack else build_audit_arguments(data),
        operation_key=idempotency_key,  # idempotency replay gate
        session_id=session_id,
        entity_id=chat_id,
        response_model=AudioStartInternalResult,
    )
