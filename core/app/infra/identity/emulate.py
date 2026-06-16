"""Emulation grant management — composes canonical black boxes.

Emulate: create grant + emulation entries for server-side identity swap.
Unemulate: consume the innermost grant to peel one layer.

resolve_identity() picks up active grants on every request and follows
the chain iteratively (supports nested emulation up to depth 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.dashboard.visibility import department_scope_allows
from app.infra.identity.resolve_identity import (
    MAX_EMULATION_DEPTH,
    resolve_emulation_chain,
)
from app.infra.identity.simulatable import SIMULATABLE_ROLES
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.emulations.create import create_emulation
from app.tools.entries.grant_consumptions.create import (
    create_grant_consumption,
)
from app.tools.entries.grants.create import create_grant
from app.tools.entries.sessions.search import search_sessions
from app.utils.logging.db_logger import get_logger
from app.utils.cache.hedged_row import transaction_with_writeback

logger = get_logger(__name__)


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
    emulation_id: UUID | None = None


async def resolve_emulation(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    requester_profile_id: UUID,
    target_profile_id: UUID,
    ttl_minutes: int = 120,
    bypass_cache: bool = False,
    actor_profile_id: UUID | None = None,
    soft: bool = False,
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

    # Step 3: Authorization check.
    #
    # Role gate (SIMULATABLE_ROLES) + DEPARTMENT scope. A non-super requester
    # may only emulate a target whose role they may simulate AND who shares one
    # of their departments (or is global/roleless) — mirroring the
    # dashboard/leaderboard boundary (#152/#148) so a dept-A admin can no longer
    # impersonate a dept-B user. Self and super-admin are unaffected:
    # department_scope_allows returns True for role_level 0, and self
    # short-circuits the whole check.
    #
    # CHAINED EMULATION (E1): when this is a second-or-later hop, the
    # ``requester`` above is the *effective* (already-emulated) profile B —
    # NOT the real actor A. Gating on B would let A launder into a role/
    # department it cannot reach directly (A→B→C where B, but not A, may
    # reach C). The authorization gate must therefore evaluate the REAL
    # ACTOR's role/departments against the final target, so A can only
    # emulate what A is directly authorized to reach regardless of hops.
    # ``actor_profile_id`` is the real JWT profile (set only while already
    # emulating); when it differs from the requester we resolve it and use
    # it as the authorizing identity. The grant linkage below stays keyed
    # on ``requester`` so resolve_emulation_chain can still walk A→B→C.
    authorizer = requester
    if actor_profile_id is not None and actor_profile_id != requester_profile_id:
        actor = await resolve_profile_identity_context(
            pool, actor_profile_id, redis, bypass_cache=bypass_cache
        )
        if not actor:
            return EmulationResult(
                allowed=False,
                reason="Actor profile not found",
                grant_id=None,
                expires_at=None,
            )
        authorizer = actor

    is_self = requester_profile_id == target_profile_id
    allowed_roles = SIMULATABLE_ROLES.get(authorizer.role, set())
    role_allowed = target.role in allowed_roles
    department_allowed = department_scope_allows(
        caller_role_level=authorizer.role_level,
        caller_department_ids=authorizer.department_ids,
        owner_role_level=target.role_level,
        owner_department_ids=target.department_ids,
    )
    is_allowed = is_self or (role_allowed and department_allowed)

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
            conn, redis, profile_ids=[requester.profiles_id], active=True, limit=1
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
            conn, redis, profile_ids=[target.profiles_id], active=True, limit=1
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
        async with transaction_with_writeback(conn):
            grant_result = await create_grant(
                conn,
                redis, session_id=requester_session_id,
                expires_at=expires_at,
                profiles_id=requester.profiles_id,
                soft=soft,
            )

            emulation_result = await create_emulation(
                conn,
                redis, grant_id=grant_result.id,
                session_id=target_session_id,
                profile_id=target.profiles_id,
                soft=soft,
            )

    # E2 — attribute the grant to the real actor in the log/audit trail so a
    # chained emulation reads "A (via B) emulated C", not "B emulated C".
    logger.info(
        "Emulation grant %s created: actor=%s requester=%s target=%s",
        grant_result.id,
        actor_profile_id or requester_profile_id,
        requester_profile_id,
        target_profile_id,
    )

    # Bust the emulation-chain cache for the requester so the next
    # request resolves their new active emulation immediately, not
    # after the 60s TTL.
    from app.infra.identity.resolve_identity import invalidate_emulation_cache
    await invalidate_emulation_cache(requester_profile_id)

    # Enqueue async refresh of grants_mv + emulations_mv via the per-MV worker.
    from app.infra.refresh.queue import enqueue_refreshes
    await enqueue_refreshes(
        pool, redis,
        profile_id=requester_profile_id,
        session_id=requester_session_id,
        artifact_type="emulation",
        targets=["grants_mv", "emulations_mv"],
    )

    return EmulationResult(
        allowed=True,
        reason=None,
        grant_id=grant_result.id,
        expires_at=expires_at,
        emulation_id=emulation_result.id,
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
    target_profile_id: UUID | None = None,
) -> UnemulationResult:
    """Consume an emulation grant to peel one layer.

    Walks the emulation chain from actor_profile_id (the real JWT profile).
    If target_profile_id is provided, consumes the grant targeting that profile.
    Otherwise falls back to consuming the innermost (last) grant.

    On the next request, resolve_identity() will resolve one layer less.
    """
    chain = await resolve_emulation_chain(pool, actor_profile_id)

    if not chain:
        return UnemulationResult(ok=False, reason="No active emulation to exit")

    # Find the grant to consume
    if target_profile_id is not None:
        link = next(
            (l for l in chain if l.target_profile_id == target_profile_id),
            None,
        )
        if link is None:
            return UnemulationResult(
                ok=False,
                reason="No active emulation found for this profile",
            )
    else:
        link = chain[-1]

    from app.infra.globals import get_redis_client
    async with pool.acquire() as conn:
        await create_grant_consumption(conn, get_redis_client(), grant_id=link.grant_id)

    # Bust the actor's cached chain so the next request sees one fewer
    # layer, not the stale 60s-TTL chain.
    from app.infra.identity.resolve_identity import invalidate_emulation_cache
    await invalidate_emulation_cache(actor_profile_id)

    logger.info(
        f"Unemulated: consumed grant {link.grant_id}, "
        f"peeled target {link.target_profile_id} "
        f"(chain depth {len(chain)} → {len(chain) - 1})"
    )

    return UnemulationResult(ok=True, reason=None)
