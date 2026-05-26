"""Profile emulate logic — composable infra architecture.

Creates an emulation grant. resolve_identity() picks it up on next request.

Soft/accept: ``soft=True`` stages the grant + emulation INACTIVE. Because
resolve_identity only follows *active* grants, a staged grant impersonates
nothing until accepted — so an agent can *propose* an emulation and a human must
accept it before the identity swap takes effect. The soft_call is keyed by the
audit server ``call_id`` (which FKs calls_entry); the ack activates the grant +
emulation and busts the emulation-chain cache so the next request picks it up.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.identity.emulate import resolve_emulation
from app.infra.profile.types import EmulateProfileApiResponse
from app.infra.refresh.queue import enqueue_refreshes
from app.infra.server_timing import timed
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.utils.cache.invalidate_tags import invalidate_tags

ARTIFACT = "profile"
OPERATION = "emulate"


async def emulate_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    target_profile_id: UUID | None = None,
    ttl_minutes: int = 120,
    bypass_cache: bool = False,
    actor_profile_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
) -> EmulateProfileApiResponse:
    """Create an emulation grant (requester -> target), with soft/accept staging.

    Raises HTTPException(403) if emulation is not allowed.
    """
    # ── Short-circuit: ack path — promote/reject a staged emulation grant ──
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404, detail="No pending emulation for this call.",
            )
        ids = entry.patch or {}
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await activate_rows(conn, table="grants_entry", ids=[UUID(ids["grant_id"])])
                    await activate_rows(conn, table="emulations_entry", ids=[UUID(ids["emulation_id"])])
            # Bust the chain cache + refresh MVs so resolve_identity picks up the
            # now-active grant on the next request (mirrors resolve_emulation).
            from app.infra.identity.resolve_identity import invalidate_emulation_cache
            await invalidate_emulation_cache(profile_id)
            await enqueue_refreshes(
                pool, redis, profile_id=profile_id, session_id=None,
                artifact_type="emulation", targets=["grants_mv", "emulations_mv"],
            )
        async with pool.acquire() as conn:
            await create_soft_call(
                conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                operation=OPERATION, artifact_id=entry.artifact_id,
                status="accepted" if accept else "rejected",
            )
        await invalidate_tags(["profile"], redis=redis)
        return EmulateProfileApiResponse(
            allowed=True,
            reason=None,
            grant_id=entry.artifact_id,
            expires_at=None,
            idempotency_key=idempotency_key,
        )

    # ── Propose (soft) / immediate (soft=False) ──
    with timed("emulation_check"):
        result = await resolve_emulation(
            pool,
            redis,
            requester_profile_id=profile_id,
            target_profile_id=target_profile_id,
            ttl_minutes=ttl_minutes,
            bypass_cache=bypass_cache,
            actor_profile_id=actor_profile_id,
            soft=soft,
        )

    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.reason or "Forbidden")

    if soft and call_id is not None and result.grant_id and result.emulation_id:
      with timed("db_write"):
        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=call_id,
                artifact=ARTIFACT,
                operation=OPERATION,
                artifact_id=result.grant_id,
                status="pending",
                patch={
                    "grant_id": str(result.grant_id),
                    "emulation_id": str(result.emulation_id),
                },
            )

    await invalidate_tags(["profile"], redis=redis)

    return EmulateProfileApiResponse(
        allowed=result.allowed,
        reason=result.reason,
        grant_id=result.grant_id,
        expires_at=result.expires_at,
        idempotency_key=call_id,
    )
