"""Emulation grant management — composes canonical black boxes.

Emulate: create grant + emulation entries for server-side identity swap.
Unemulate: consume the innermost grant to peel one layer.

resolve_identity() picks up active grants on every request and follows
the chain iteratively (supports nested emulation up to depth 5).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.identity.resolve_identity import (
    MAX_EMULATION_DEPTH,
    resolve_emulation_chain,
)
from app.infra.identity.simulatable import SIMULATABLE_ROLES
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.emulations.create import create_emulation
from app.tools.entries.emulations.refresh import refresh_emulations
from app.tools.entries.grant_consumptions.create import (
    create_grant_consumption,
)
from app.tools.entries.grants.create import create_grant
from app.tools.entries.sessions.search import search_sessions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Emulate — create a new emulation layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmulationResult:
    """Result of an emulation grant creation."""

    allowed: bool
    reason: str | None
    grant_id: UUID | None
    expires_at: datetime | None


async def resolve_emulation(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    requester_profile_id: UUID,
    target_profile_id: UUID,
    ttl_minutes: int = 120,
    bypass_cache: bool = False,
    actor_profile_id: UUID | None = None,
) -> EmulationResult:
    """Create an emulation grant using canonical black boxes.

    Returns an EmulationResult with allowed=False if authorization fails.
    On success, resolve_identity() will pick up the grant on the next request.

    Uses actor_profile_id (the real JWT profile) to check depth limit.
    """
    # Depth check — walk chain from the original profile
    origin = actor_profile_id or requester_profile_id
    chain = await resolve_emulation_chain(pool, origin)
    if len(chain) >= MAX_EMULATION_DEPTH:
        return EmulationResult(
            allowed=False,
            reason=f"Maximum emulation depth ({MAX_EMULATION_DEPTH}) reached",
            grant_id=None,
            expires_at=None,
        )

    # Step 1: Resolve requester identity
    requester = await resolve_profile_identity_context(
        pool, requester_profile_id, redis, bypass_cache=bypass_cache
    )
    if not requester:
        return EmulationResult(
            allowed=False,
            reason="Requester profile not found",
            grant_id=None,
            expires_at=None,
        )

    # Step 2: Resolve target identity
    target = await resolve_profile_identity_context(
        pool, target_profile_id, redis, bypass_cache=bypass_cache
    )
    if not target:
        return EmulationResult(
            allowed=False,
            reason="Target profile not found",
            grant_id=None,
            expires_at=None,
        )

    # Step 3: Authorization check
    is_self = requester_profile_id == target_profile_id
    allowed_roles = SIMULATABLE_ROLES.get(requester.role, set())
    is_allowed = is_self or target.role in allowed_roles

    if not is_allowed:
        return EmulationResult(
            allowed=False,
            reason="You do not have permission to emulate this profile",
            grant_id=None,
            expires_at=None,
        )

    # Step 4: Find active sessions for requester and target
    async with pool.acquire() as conn:
        requester_sessions = await search_sessions(
            conn, profile_ids=[requester.profiles_id], active=True, limit=1
        )
    if not requester_sessions:
        return EmulationResult(
            allowed=False,
            reason="No active session found for requester",
            grant_id=None,
            expires_at=None,
        )

    async with pool.acquire() as conn:
        target_sessions = await search_sessions(
            conn, profile_ids=[target.profiles_id], active=True, limit=1
        )
    if not target_sessions:
        return EmulationResult(
            allowed=False,
            reason="No active session found for target",
            grant_id=None,
            expires_at=None,
        )

    requester_session_id = requester_sessions[0].id
    target_session_id = target_sessions[0].id

    # Step 5: Create grant + emulation in a single transaction
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl_minutes)
    async with pool.acquire() as conn:
        async with conn.transaction():
            grant_result = await create_grant(
                conn,
                session_id=requester_session_id,
                expires_at=expires_at,
                profiles_id=requester.profiles_id,
            )

            await create_emulation(
                conn,
                grant_id=grant_result.id,
                session_id=target_session_id,
                profile_id=target.profiles_id,
            )

    async with pool.acquire() as conn:
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY grants_mv")
        await refresh_emulations(conn)

    return EmulationResult(
        allowed=True,
        reason=None,
        grant_id=grant_result.id,
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# Unemulate — consume the innermost grant to peel one layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UnemulationResult:
    """Result of an unemulation (consuming a grant)."""

    ok: bool
    reason: str | None


async def resolve_unemulation(
    pool: asyncpg.Pool,
    *,
    actor_profile_id: UUID,
) -> UnemulationResult:
    """Consume the innermost emulation grant to peel one layer.

    Walks the emulation chain from actor_profile_id (the real JWT profile),
    finds the last grant in the chain, and creates a consumption for it.

    On the next request, resolve_identity() will resolve one layer less.
    """
    chain = await resolve_emulation_chain(pool, actor_profile_id)

    if not chain:
        return UnemulationResult(ok=False, reason="No active emulation to exit")

    # Consume the innermost (last) grant in the chain
    innermost = chain[-1]

    async with pool.acquire() as conn:
        await create_grant_consumption(conn, grant_id=innermost.grant_id)

    logger.info(
        f"Unemulated: consumed grant {innermost.grant_id}, "
        f"peeled target {innermost.target_profile_id} "
        f"(chain depth {len(chain)} → {len(chain) - 1})"
    )

    return UnemulationResult(ok=True, reason=None)
