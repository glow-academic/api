"""Invocation decrypt logic — composable infra architecture.

Authorizes the caller, validates the key belongs to the invocation, then
delegates to resolve_decrypt.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.identity.decrypt import resolve_decrypt
from app.infra.invocation.types import DecryptInvocationKeyApiResponse
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
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
      1. Authorize — caller must hold the test:invocation_draft permission
         (revealing a raw invocation key is a privileged read tied to the
         invocation editor where the reveal action lives; editing the
         invocation's keys is gated on this same permission).
      2. Validate the key belongs to the invocation (get_invocations)
      3. resolve_decrypt — profile identity check + actual decryption
      4. Return typed response
    """
    # ── Step 1: Authorize the caller ──────────────────────────────────
    # The route/WS layer only guarantees an *authenticated* profile; it
    # does NOT gate by role. Without this check any signed-in user could
    # reveal an invocation's raw API-key secret.
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, bypass_cache=bypass_cache
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )
    if not has_permission(profile.role_permissions, "test", "invocation_draft"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to reveal invocation keys.",
        )

    # ── Step 2: Validate key belongs to invocation ────────────────────
    with timed("hydrate"):
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
    with timed("build"):
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
