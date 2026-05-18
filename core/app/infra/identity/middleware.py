"""Unified auth middleware — resolves identity on every request.

Validates JWT (Authorization: Bearer), then sets:
  - request.state.profile_id
  - request.state.session_id
  - request.state.identity

group_id and run_id are NOT resolved here — they are stateless and
derived by each infra function from the entity being operated on
(e.g., invocation_id → test → call → run → group).

Uses FastAPI security utilities so the OpenAPI spec includes proper
securitySchemes (http/bearer) on every protected endpoint.

Also debounce-writes an ``activity_entry`` row per authenticated
request — Redis SETNX gates at one write per minute per profile, so
the session resolver has a fresh "last seen" anchor for its idle
check without amplifying writes on hot endpoints.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import os
from uuid import UUID

import asyncpg  # type: ignore
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis

from app.infra.globals import get_pool, get_redis_client
from app.infra.identity.resolve_identity import (
    Identity,
    get_or_create_session,
    resolve_identity,
)
from app.infra.profile_identity_context import resolve_profile_identity_context

logger = logging.getLogger(__name__)

# ── E2E auth bypass ──────────────────────────────────────────────
# Gated by env. When ``E2E_BYPASS_TOKEN`` is set, requests with a
# matching ``Authorization: Bearer <token>`` are accepted without
# JWT verification, resolving to the bootstrap superadmin profile by
# default. Tests can target a different profile by sending
# ``X-E2E-Profile-Id: <uuid>`` — the middleware verifies the profile
# exists in the DB and refuses otherwise.
#
# This MUST be unset in production. The middleware logs a loud
# warning at first activation so accidental enablement is obvious
# in the logs of any restart.
_E2E_BYPASS_TOKEN = os.getenv("E2E_BYPASS_TOKEN", "").strip()
_E2E_BYPASS_ENABLED = bool(_E2E_BYPASS_TOKEN)
# Default profile_artifact id to impersonate when X-E2E-Profile-Id is
# not provided. Setup-specific — the right UUID depends on which seed
# the user restored (fresh/university/organization each create their
# own superadmin artifact). User puts the right one in
# E2E_BYPASS_PROFILE_ID. No silent fallback: enabling bypass without
# this set logs a loud warning and any unrouted request errors with
# a clear "missing E2E_BYPASS_PROFILE_ID" message.
_E2E_DEFAULT_PROFILE_ID_RAW = os.getenv("E2E_BYPASS_PROFILE_ID", "").strip()
_E2E_DEFAULT_PROFILE_ID: UUID | None = None
if _E2E_DEFAULT_PROFILE_ID_RAW:
    try:
        _E2E_DEFAULT_PROFILE_ID = UUID(_E2E_DEFAULT_PROFILE_ID_RAW)
    except ValueError:
        logger.error(
            "E2E_BYPASS_PROFILE_ID is not a valid UUID: %r — bypass requests "
            "without an X-E2E-Profile-Id header will fail.",
            _E2E_DEFAULT_PROFILE_ID_RAW,
        )
if _E2E_BYPASS_ENABLED:
    logger.warning(
        "⚠️  E2E_BYPASS_TOKEN is set — auth bypass enabled "
        "(default profile %s). NEVER enable in production.",
        _E2E_DEFAULT_PROFILE_ID or "(unset — pass X-E2E-Profile-Id per request)",
    )
from app.tools.entries.activity.create import create_activity
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

# Activity-ping throttle. One write per minute per profile is plenty
# for the 10-minute session-idle check — the worst-case staleness on
# ``max(activity_entry.created_at)`` is ~1 min, so the effective idle
# window is 9-10 min in practice. Tune in concert with
# ``SESSION_IDLE_MINUTES`` in resolve_identity.py.
_ACTIVITY_THROTTLE_SECONDS = 60


async def _maybe_ping_activity(
    pool: asyncpg.Pool,
    redis: Redis,
    profile_id: UUID,
    session_id: UUID,
) -> None:
    """Fire-and-forget activity ping, debounced via Redis SETNX.

    Best-effort: never raise back into the request path. The session
    resolver gracefully falls back to ``sessions_entry.created_at`` if
    no activity rows exist yet, so a skipped or failed ping just
    means the idle window is measured from session-start rather than
    last-activity for that minute window.
    """
    try:
        key = f"glow:activity:write:{profile_id}"
        ok = await redis.set(key, "1", nx=True, ex=_ACTIVITY_THROTTLE_SECONDS)
        if not ok:
            return
        async with pool.acquire() as conn:
            await create_activity(
                conn,
                session_id=session_id,
                profile_id=profile_id,
            )
    except Exception as e:
        logger.warning(f"activity ping failed for profile={profile_id}: {e}")

# OpenAPI security scheme — generates securitySchemes in the spec
_bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    bearerFormat="JWT",
    description="Keycloak-issued JWT token. Resolves the caller's profile and session.",
    auto_error=False,
)


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> Identity:
    """FastAPI dependency that validates auth and resolves identity.

    Requires:
      - Authorization: Bearer <jwt> (user identity, always required)

    SSE callers that can't set headers (browser ``EventSource``) must
    proxy through the client's BFF route at ``/api/stream/{artifact}``,
    which attaches the Bearer header server-side. We deliberately do
    NOT accept a ``?token=`` query fallback — that would leak the JWT
    through server logs, browser history, and Referer headers.

    Sets on request.state:
      - profile_id: UUID
      - session_id: UUID
      - identity: full Identity object

    Raises:
        HTTPException 401 if auth is missing or invalid
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization: Bearer <token> header",
        )

    pool = get_pool()

    # E2E bypass — short-circuits JWT verification when the env-gated
    # bypass token matches. See module-level docstring for safety
    # invariants. Per-test profile selection via X-E2E-Profile-Id.
    # Composes the existing identity helpers — no new DB access here.
    if _E2E_BYPASS_ENABLED and hmac.compare_digest(
        credentials.credentials, _E2E_BYPASS_TOKEN
    ):
        header_profile = request.headers.get("X-E2E-Profile-Id", "").strip()
        if header_profile:
            try:
                profile_id = UUID(header_profile)
            except ValueError as e:
                raise HTTPException(
                    status_code=401,
                    detail=f"E2E bypass: invalid X-E2E-Profile-Id ({header_profile!r})",
                ) from e
        elif _E2E_DEFAULT_PROFILE_ID is not None:
            profile_id = _E2E_DEFAULT_PROFILE_ID
        else:
            raise HTTPException(
                status_code=401,
                detail="E2E bypass: no profile to impersonate. Set E2E_BYPASS_PROFILE_ID "
                "in the api .env or send X-E2E-Profile-Id on the request.",
            )
        redis = get_redis_client()
        profile_ctx = await resolve_profile_identity_context(pool, profile_id, redis)
        if profile_ctx is None:
            raise HTTPException(
                status_code=401,
                detail=f"E2E bypass: profile {profile_id} not found in DB. "
                "Reseed or pass a real X-E2E-Profile-Id.",
            )
        async with pool.acquire() as conn:
            session_id = await get_or_create_session(conn, profile_id)
        identity = Identity(
            profile_id=profile_id,
            session_id=session_id,
            email=profile_ctx.primary_email,
            role=profile_ctx.role,
        )
        request.state.profile_id = str(identity.profile_id)
        request.state.session_id = str(identity.session_id)
        request.state.identity = identity
        return identity

    try:
        identity = await resolve_identity(credentials.credentials, pool)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    request.state.profile_id = str(identity.profile_id)
    request.state.session_id = str(identity.session_id)
    request.state.identity = identity

    # Debounced activity ping. Fire-and-forget so the request isn't
    # blocked on a DB write that only happens once per minute per
    # profile anyway. Throttle is keyed on profile_id in Redis.
    asyncio.create_task(
        _maybe_ping_activity(
            pool,
            get_redis_client(),
            identity.profile_id,
            identity.session_id,
        )
    )

    return identity
