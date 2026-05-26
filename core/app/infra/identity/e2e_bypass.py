"""E2E auth bypass — shared by the resource-endpoint auth dependency
(``require_auth`` in ``identity/middleware.py``) and the MCP middleware
(``McpOAuthMiddleware`` in ``infra/mcp/oauth.py``).

Gated by env. When ``E2E_BYPASS_TOKEN`` is set, a request whose Bearer
token matches (constant-time) is accepted without JWT verification,
resolving to the bootstrap superadmin profile (``E2E_BYPASS_PROFILE_ID``)
by default, or to ``X-E2E-Profile-Id`` per request. The profile is
verified to exist in the DB and refused otherwise.

This MUST be unset in production. When unset, ``try_e2e_bypass`` returns
``None`` so every caller falls through to normal JWT auth — the single
prod-safety gate for both the resource endpoints and MCP. A loud warning
is logged at first import so accidental enablement is obvious in the logs
of any restart.
"""

from __future__ import annotations

import hmac
import logging
import os
from uuid import UUID

from fastapi import HTTPException, Request

from app.infra.globals import get_pool, get_redis_client
from app.infra.identity.resolve_identity import Identity, get_or_create_session
from app.infra.profile_identity_context import resolve_profile_identity_context

logger = logging.getLogger(__name__)

_E2E_BYPASS_TOKEN = os.getenv("E2E_BYPASS_TOKEN", "").strip()
_E2E_BYPASS_ENABLED = bool(_E2E_BYPASS_TOKEN)
# Default profile_artifact id to impersonate when X-E2E-Profile-Id is not
# provided. Setup-specific (fresh/university/organization seed each create
# their own superadmin artifact) — the user puts the right UUID in
# E2E_BYPASS_PROFILE_ID. No silent fallback.
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


async def try_e2e_bypass(request: Request, token: str | None) -> Identity | None:
    """If the env-gated E2E bypass applies to ``token``, resolve the
    impersonated profile, set ``request.state`` (profile_id / session_id /
    identity), and return its ``Identity``.

    Returns ``None`` when the bypass is disabled or the token doesn't
    match — the caller then proceeds with normal JWT verification.

    Raises ``HTTPException(401)`` only when the bypass token matches but
    the requested profile is invalid or not present in the DB.
    """
    if not (
        _E2E_BYPASS_ENABLED
        and token
        and hmac.compare_digest(token, _E2E_BYPASS_TOKEN)
    ):
        return None

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

    pool = get_pool()
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
