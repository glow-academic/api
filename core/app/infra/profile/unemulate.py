"""Profile unemulate logic — composable infra architecture.

Consumes the innermost emulation grant to peel one layer.

Soft/accept (record-and-hold): unemulation is an *action* (consuming a grant),
not a row to stage — so ``soft=True`` records the intent in a pending soft_call
(keyed by the audit server ``call_id``) WITHOUT consuming; the emulation keeps
working until the ack performs it. ``accept=True`` runs resolve_unemulation;
reject discards the proposal. (This is the same record-and-hold shape as refresh.)
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.identity.emulate import resolve_unemulation
from app.infra.profile.types import UnemulateProfileApiResponse
from app.infra.server_timing import timed
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.utils.cache.invalidate_tags import invalidate_tags

ARTIFACT = "profile"
OPERATION = "unemulate"


async def unemulate_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    actor_profile_id: UUID | None = None,
    target_profile_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
) -> UnemulateProfileApiResponse:
    """Exit emulation for a specific profile (or innermost layer), with soft/accept.

    Raises HTTPException(400) if unemulation fails.
    """
    origin = actor_profile_id or profile_id

    # ── Short-circuit: ack path — perform / discard the proposed unemulation ──
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404, detail="No pending unemulation for this call.",
            )
        ids = entry.patch or {}
        if accept:
            result = await resolve_unemulation(
                pool,
                actor_profile_id=origin,
                target_profile_id=ids.get("target_profile_id"),
            )
            if not result.ok:
                raise HTTPException(
                    status_code=400, detail=result.reason or "Cannot exit emulation",
                )
        async with pool.acquire() as conn:
            await create_soft_call(
                conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                operation=OPERATION, artifact_id=entry.artifact_id,
                status="accepted" if accept else "rejected",
            )
        await invalidate_tags(["profile"], redis=redis)
        return UnemulateProfileApiResponse(ok=True, reason=None, idempotency_key=idempotency_key)

    # ── Propose (soft): record the intent, do NOT consume the grant yet ──
    if soft and call_id is not None:
        async with pool.acquire() as conn:
            await create_soft_call(
                conn, redis, call_id=call_id, artifact=ARTIFACT, operation=OPERATION,
                artifact_id=origin, status="pending",
                patch={"target_profile_id": str(target_profile_id) if target_profile_id else None},
            )
        return UnemulateProfileApiResponse(
            ok=True, reason="Unemulation proposed (pending acceptance)",
            idempotency_key=call_id,
        )

    # ── Immediate (soft=False): consume now (original behavior) ──
    with timed("emulation_check"):
        result = await resolve_unemulation(
            pool,
            actor_profile_id=origin,
            target_profile_id=target_profile_id,
        )

    if not result.ok:
        raise HTTPException(
            status_code=400, detail=result.reason or "Cannot exit emulation",
        )

    await invalidate_tags(["profile"], redis=redis)

    return UnemulateProfileApiResponse(
        ok=result.ok, reason=result.reason, idempotency_key=call_id,
    )
