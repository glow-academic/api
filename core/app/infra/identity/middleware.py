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
from uuid import UUID

import asyncpg  # type: ignore
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis

from app.infra.globals import get_pool, get_redis_client
from app.infra.identity.e2e_bypass import try_e2e_bypass
from app.infra.identity.resolve_identity import (
    Identity,
    resolve_identity,
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
                redis, session_id=session_id,
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
    # bypass token matches. Shared with the MCP middleware via
    # app/infra/identity/e2e_bypass.py (single prod-safety gate).
    # Returns None when disabled or the token doesn't match, so we fall
    # through to normal JWT verification below.
    identity = await try_e2e_bypass(request, credentials.credentials)
    if identity is not None:
        return identity

    from app.infra.server_timing import timed
    try:
        with timed("auth"):
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
