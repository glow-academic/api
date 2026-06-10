"""Attempt complete — marks an entire attempt as completed.

Idempotent primitive: creates attempt_completion_entry if not already present.

Soft/accept (stage-inactive): ``soft=True`` creates the completion row dormant
(``active=False``) + a pending ``soft_calls_entry`` keyed by the audit server
``call_id``; the ack ({idempotency_key, accept}) activates it (or rejects). The
completion isn't "real" until accepted — so an agent can propose completing an
attempt and a human accepts. ``soft=False`` completes immediately (original).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.attempt.permissions import check_attempt_access
from app.infra.attempt.refresh import refresh_attempt_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.attempt.search import search_attempts
from app.tools.entries.attempt_completion.create import create_attempt_completion
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call

ARTIFACT = "attempt"
OPERATION = "complete"


async def complete_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    attempt_id: UUID | None = None,
    message: str = "",
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
    **kwargs: Any,
):
    """Mark an attempt as completed (with soft/accept staging)."""
    if attempt_id is None and "attempt_id" in kwargs:
        attempt_id = kwargs["attempt_id"]
    if isinstance(attempt_id, str):
        attempt_id = UUID(attempt_id)

    # ── Short-circuit: ack — activate / reject a staged completion ──
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(status_code=404, detail="No pending completion for this call.")
        ids = entry.patch or {}
        if accept:
            async with pool.acquire() as conn:
                await activate_rows(conn, table="attempt_completion_entry", ids=[UUID(ids["completion_id"])])
            await refresh_attempt_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                targets=["attempt_completion_mv", "attempt_mv"],
            )
        async with pool.acquire() as conn:
            await create_soft_call(
                conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                operation=OPERATION, artifact_id=entry.artifact_id,
                status="accepted" if accept else "rejected",
            )
        return {
            "success": True,
            "completion_id": str(ids.get("completion_id", "")),
            "attempt_id": str(ids.get("attempt_id", "")),
            "idempotency_key": idempotency_key,
        }

    if not attempt_id:
        raise ValueError("attempt_id is required")

    # ── Owner/role scope (BOLA guard) ─────────────────────────────────────
    # ``require_auth`` only proves the caller is *some* authenticated profile;
    # the completion insert below is keyed solely by the caller-supplied
    # ``attempt_id`` and is NOT scoped to the actor. Without this, any
    # authenticated profile could flip another student's attempt to terminal
    # ``completed`` simply by passing their ``attempt_id``. Mirror the
    # owner-or-strictly-higher-role gate that the sibling ``POST /attempt/
    # archive`` (``archive_attempt_impl``) and the read side
    # (``get_attempt_internal`` / ``enforce_attempt_media_access``, issue #148)
    # enforce: resolve the attempt's owner and only allow the actor who owns it
    # or strictly outranks the owner.
    requester = await resolve_profile_identity_context(pool, profile_id, redis)
    async with pool.acquire() as conn:
        attempts, _ = await search_attempts(
            conn, redis, attempt_ids=[attempt_id], limit=1, offset=0,
        )
    # ``attempt_mv.profile_id`` (a.profile_id) is the owner's *resource*
    # profiles_id, so compare against ``requester.profiles_id`` (NOT the
    # artifact profile_id) — exactly as ``archive_attempt_impl`` does.
    owner_profiles_id = attempts[0].profile_id if attempts else None
    requester_profiles_id = requester.profiles_id if requester else None
    if requester_profiles_id is None or not check_attempt_access(
        owner_profiles_id,
        requester_profiles_id,
        request_role=requester.role if requester else None,
        attempt_role=None,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this resource.",
        )

    # ── Propose (soft) / immediate (soft=False) ──
    with timed("db_write"):
        async with pool.acquire() as conn:
            result = await create_attempt_completion(
                conn,
                redis, attempt_id=attempt_id,
                session_id=session_id,
                message=message,
                soft=soft,
            )
            if soft and call_id is not None:
                await create_soft_call(
                    conn, redis, call_id=call_id, artifact=ARTIFACT,
                    operation=OPERATION, artifact_id=result.id, status="pending",
                    patch={"completion_id": str(result.id), "attempt_id": str(attempt_id)},
                )

    with timed("refresh"):
        await refresh_attempt_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["attempt_completion_mv", "attempt_mv"],
        )

    return {
        "success": True,
        "completion_id": str(result.id),
        "attempt_id": str(attempt_id),
        "idempotency_key": call_id,
    }
