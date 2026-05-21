"""Invocation decrypt logic — composable infra architecture.

Validates the key belongs to the invocation, then delegates to resolve_decrypt.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.identity.decrypt import resolve_decrypt
from app.infra.invocation.types import DecryptInvocationKeyApiResponse
from app.tools.entries.invocation.get import get_invocations


async def decrypt_invocation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    invocation_id: UUID,
    key_id: UUID,
    bypass_cache: bool = False,
) -> DecryptInvocationKeyApiResponse:
    """Decrypt a key scoped to an invocation entry.

    Flow:
      1. Validate the key belongs to the invocation (get_invocations)
      2. resolve_decrypt — profile identity check + actual decryption
      3. Return typed response
    """
    # ── Step 1: Validate key belongs to invocation ────────────────────
    async with pool.acquire() as conn:
        invocations = await get_invocations(conn, [invocation_id], redis)

    if not invocations:
        raise HTTPException(status_code=404, detail="Invocation not found")

    invocation = invocations[0]
    if key_id not in (invocation.key_ids or []):
        raise HTTPException(
            status_code=403,
            detail="Key does not belong to this invocation",
        )

    # ── Step 2: Decrypt ───────────────────────────────────────────────
    result = await resolve_decrypt(
        pool,
        redis,
        profile_id=profile_id,
        key_id=key_id,
        bypass_cache=bypass_cache,
    )

    return DecryptInvocationKeyApiResponse(
        key=result.key,
        name=result.name,
        actor_name=result.actor_name,
    )
