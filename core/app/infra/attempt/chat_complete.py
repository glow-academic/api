"""Attempt chat complete — marks a chat as completed.

Model calls this explicitly when it determines the chat is done.

Soft/accept (stage-inactive): ``soft=True`` writes the completion row dormant
(``active=False``) + a pending ``soft_calls_entry``; the ack activates it or
rejects. Mirrors attempt/complete + invocation_complete.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.attempt.permissions import enforce_attempt_access_by_chat
from app.infra.attempt.refresh import refresh_attempt_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.attempt_chat_completion.create import (
    create_attempt_chat_completion,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "attempt"
OPERATION = "chat_complete"


async def chat_complete_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    chat_id: UUID | None = None,
    message: str = "",
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
    **kwargs: Any,
):
    """Mark an attempt chat as completed (with soft/accept)."""
    # ── Short-circuit: ack — activate / reject the staged completion ──
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(status_code=404, detail="No pending chat completion for this call.")
        ids = entry.patch or {}
        completion_id = ids.get("completion_id")
        if accept and completion_id:
            async with pool.acquire() as conn:
                await activate_rows(conn, table="attempt_chat_completion_entry", ids=[UUID(completion_id)])
            await refresh_attempt_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                targets=["attempt_chat_completion_mv", "attempt_chat_mv"],
            )
        async with pool.acquire() as conn:
            await create_soft_call(
                conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                operation=OPERATION, artifact_id=entry.artifact_id,
                status="accepted" if accept else "rejected",
            )
        return {
            "completion_id": str(completion_id or ""),
            "chat_id": str(ids.get("chat_id", "")),
            "idempotency_key": str(idempotency_key),
        }

    if chat_id is None and "chat_id" in kwargs:
        chat_id = UUID(kwargs["chat_id"])
    if isinstance(chat_id, str):
        chat_id = UUID(chat_id)
    if not chat_id:
        raise ValueError("chat_id is required")

    # Authorization (was MISSING — keyed solely by caller-supplied chat_id, this
    # flips a chat to terminal ``completed`` with no actor scope, the A2-class
    # sibling of attempt/complete + the dept-blind archive). Route through the
    # shared chat-keyed gate: resolve chat → owner and enforce
    # self/super-admin/strictly-higher-role-in-department.
    requester = await resolve_profile_identity_context(pool, profile_id, redis)
    await enforce_attempt_access_by_chat(pool, redis, chat_id=chat_id, requester=requester)

    with timed("db_write"):
        async with pool.acquire() as conn:
            async with transaction_with_writeback(conn):
                result = await create_attempt_chat_completion(
                    conn,
                    redis, chat_id=chat_id,
                    session_id=session_id,
                    message=message,
                    soft=soft,
                )
                if soft and call_id is not None:
                    await create_soft_call(
                        conn, redis, call_id=call_id, artifact=ARTIFACT,
                        operation=OPERATION, artifact_id=result.id, status="pending",
                        patch={"completion_id": str(result.id), "chat_id": str(chat_id)},
                    )

    if not soft:
        with timed("refresh"):
            await refresh_attempt_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                targets=["attempt_chat_completion_mv", "attempt_chat_mv"],
            )

    return {
        "completion_id": str(result.id),
        "chat_id": str(chat_id),
        "idempotency_key": str(call_id) if call_id else None,
    }
