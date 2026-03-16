"""Unified identity resolution — single entry point for HTTP + Socket.IO.

Resolves a Bearer JWT token into a profile_id + session_id. Used by:
  - HTTP middleware (replaces get_profile_id + get_session_id dependencies)
  - Socket.IO connect handler (replaces query string params)
  - Background tasks (system session)

The JWT is issued by Keycloak (via default_idp or external IdP). The token
contains either a profile_id claim (from default_idp) or an email claim
(from external IdPs), which we resolve to a local profile_id.
"""

from __future__ import annotations

import logging
import os
import socket
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg
import requests
from jose import jwt

from app.infra.identity.keycloak_sync import get_idp_public_url

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (same env vars as mcp/oauth.py)
# ---------------------------------------------------------------------------

ORIGIN = os.getenv("ORIGIN", "http://localhost")
APP_PREFIX = os.getenv("APP_PREFIX", "")
KEYCLOAK_INTERNAL_URL = os.getenv("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "master")
KEYCLOAK_ISSUER = f"{ORIGIN}{APP_PREFIX}/auth/realms/{KEYCLOAK_REALM}"

# JWKS URLs — try multiple endpoints for different environments
JWKS_URLS = [
    f"{KEYCLOAK_INTERNAL_URL}/auth/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs",
    "http://localhost:8080/auth/realms/master/protocol/openid-connect/certs",
    f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs",
]

# Also accept tokens from the built-in default-idp.
# Keep issuer validation aligned with the actual default-idp public URL.
_default_idp_base = get_idp_public_url()

# JWKS cache (shared across calls)
_jwks_cache: dict[str, Any] = {"keys": None, "ts": 0.0, "url": None}
_JWKS_TTL = 60  # seconds

# System session (created once at startup for background tasks)
_system_session_id: UUID | None = None


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmulationChainLink:
    """One hop in the emulation chain."""

    grant_id: UUID
    target_profile_id: UUID


@dataclass(frozen=True)
class Identity:
    """Resolved identity from a JWT token."""

    profile_id: UUID
    session_id: UUID
    email: str | None = None
    role: str | None = None
    is_emulation: bool = False
    actor_profile_id: UUID | None = None
    emulation_depth: int = 0
    is_mcp: bool = False


# ---------------------------------------------------------------------------
# JWKS fetching (reused from mcp/oauth.py pattern)
# ---------------------------------------------------------------------------


def _can_resolve_hostname(hostname: str) -> bool:
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.gaierror:
        return False


def _get_jwks() -> list[dict[str, Any]]:
    """Get JWKS keys from Keycloak + default-idp with caching."""
    now = time.time()
    if _jwks_cache["keys"] is not None and now - _jwks_cache["ts"] <= _JWKS_TTL:
        return _jwks_cache["keys"]

    all_keys: list[dict[str, Any]] = []

    # Fetch from Keycloak
    urls_to_try = []
    for url in JWKS_URLS:
        if "keycloak:8080" in url and not _can_resolve_hostname("keycloak"):
            continue
        urls_to_try.append(url)

    for jwks_url in urls_to_try:
        try:
            response = requests.get(jwks_url, timeout=5)
            response.raise_for_status()
            keys = response.json().get("keys", [])
            if keys:
                all_keys.extend(keys)
                logger.debug(f"Fetched {len(keys)} keys from {jwks_url}")
                break
        except Exception as e:
            logger.debug(f"Failed to fetch JWKS from {jwks_url}: {e}")
            continue

    # Also include the built-in default-idp keys from the canonical infra module.
    try:
        from app.infra.identity.jwks import get_jwks as get_default_idp_jwks

        default_keys = get_default_idp_jwks().get("keys", [])
        all_keys.extend(default_keys)
    except Exception as e:
        logger.debug(f"Failed to get default-idp JWKS: {e}")

    if all_keys:
        _jwks_cache["keys"] = all_keys
        _jwks_cache["ts"] = now
        return all_keys

    # Fall back to cached keys if available
    if _jwks_cache["keys"] is not None:
        logger.warning("Failed to refresh JWKS, using cached keys")
        return _jwks_cache["keys"]

    raise RuntimeError("Failed to fetch JWKS from all endpoints")


# ---------------------------------------------------------------------------
# JWT verification
# ---------------------------------------------------------------------------


def verify_jwt(token: str) -> dict[str, Any]:
    """Verify a JWT token and return its claims.

    Accepts tokens from Keycloak or the built-in default-idp.

    Raises:
        ValueError: If token is invalid, expired, or unverifiable.
    """
    try:
        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid")
        if not kid:
            raise ValueError("Token missing kid header")

        keys = _get_jwks()
        key = next((k for k in keys if k.get("kid") == kid), None)
        if not key:
            raise ValueError(f"No matching JWK found for kid={kid}")

        claims = jwt.decode(
            token,
            key,
            algorithms=[headers.get("alg", "RS256")],
            options={
                "verify_at_hash": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )

        # Validate issuer — accept Keycloak and default-idp issuers
        token_issuer = claims.get("iss", "")
        expected_issuers = [
            KEYCLOAK_ISSUER,
            f"{KEYCLOAK_INTERNAL_URL}/auth/realms/{KEYCLOAK_REALM}",
            "http://localhost:8080/auth/realms/master",
            _default_idp_base,
        ]

        if token_issuer and not any(
            _issuer_matches(token_issuer, expected) for expected in expected_issuers
        ):
            logger.warning(
                f"Token issuer mismatch: got {token_issuer}, "
                f"expected one of {expected_issuers}"
            )
            raise ValueError(f"Token issuer {token_issuer} not recognized")

        return claims

    except jwt.ExpiredSignatureError as e:
        raise ValueError("Token expired") from e
    except jwt.JWTClaimsError as e:
        raise ValueError(f"Token claims invalid: {e}") from e
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Token verification failed: {e}") from e


def _issuer_matches(actual: str, expected: str) -> bool:
    """Flexible issuer comparison (handles port differences in dev)."""
    if actual == expected:
        return True
    # Strip common dev ports for comparison
    actual_norm = actual.replace(":8080", "").replace(":3000", "").replace(":8000", "")
    expected_norm = (
        expected.replace(":8080", "").replace(":3000", "").replace(":8000", "")
    )
    return actual_norm == expected_norm


# ---------------------------------------------------------------------------
# Identity resolution
# ---------------------------------------------------------------------------


async def resolve_identity(token: str, pool: asyncpg.Pool) -> Identity:
    """Resolve a Bearer JWT token to a full Identity.

    1. Verify JWT signature
    2. Extract profile_id from claims (direct or via email lookup)
    3. Get or create a session for this profile

    Args:
        token: JWT token string (without "Bearer " prefix)
        pool: Database pool

    Returns:
        Identity with profile_id, session_id, and metadata

    Raises:
        ValueError: If token is invalid or profile cannot be resolved
    """
    claims = verify_jwt(token)

    # Resolve profile_id
    profile_id = await _resolve_profile_id(claims, pool)

    # Auto-create guest profile if email exists but no profile found
    if profile_id is None:
        profile_id = await _auto_create_guest_profile(claims, pool)

    if profile_id is None:
        raise ValueError(
            f"No profile found for token claims (email={claims.get('email')})"
        )

    # Check for active emulation override (admin viewing as another profile)
    actor_profile_id: UUID | None = None
    is_emulation = False
    emulation_depth = 0
    chain = await resolve_emulation_chain(pool, profile_id)
    if chain:
        actor_profile_id = profile_id
        profile_id = chain[-1].target_profile_id
        is_emulation = True
        emulation_depth = len(chain)

    # Get or create session for the effective profile
    async with pool.acquire() as conn:
        session_id = await _get_or_create_session(conn, profile_id)

    return Identity(
        profile_id=profile_id,
        session_id=session_id,
        email=claims.get("email"),
        role=claims.get("role"),
        is_emulation=is_emulation,
        actor_profile_id=actor_profile_id,
        emulation_depth=emulation_depth,
    )


async def _resolve_profile_id(
    claims: dict[str, Any], pool: asyncpg.Pool
) -> UUID | None:
    """Extract profile_id from JWT claims.

    Strategy:
    1. Direct profile_id claim (from default_idp tokens)
    2. Email lookup via black box functions (from external IdP tokens)
    """
    # Strategy 1: Direct profile_id in claims (default_idp puts it there)
    direct_id = claims.get("profile_id")
    if direct_id:
        try:
            return UUID(direct_id)
        except ValueError:
            pass

    # Strategy 2: Look up by email using black box functions
    email = claims.get("email")
    if not email:
        return None

    from app.infra.globals import get_redis_client
    from app.tools.artifacts.profile.search import search_profiles
    from app.tools.resources.emails.search import search_emails

    redis = get_redis_client()

    async with pool.acquire() as conn:
        email_results = await search_emails(conn, redis, search=email, limit_count=100)

    matching_email_ids = [
        e.id for e in email_results if e.email.lower() == email.lower()
    ]
    if not matching_email_ids:
        return None

    async with pool.acquire() as conn:
        artifact_ids, _ = await search_profiles(
            conn, email_ids=matching_email_ids, active_only=False, limit_count=1
        )

    return artifact_ids[0] if artifact_ids else None


async def _auto_create_guest_profile(
    claims: dict[str, Any], pool: asyncpg.Pool
) -> UUID | None:
    """Auto-create a guest profile from JWT claims when no profile exists.

    Extracts department_id from the Keycloak client ID (azp claim):
      - "glow-client-{department_id}" → assign to that department
      - "glow-client" or other → no department (admin assigns later)

    Uses resolve_profile_upsert (existing black box) — no inline SQL.
    """
    email = claims.get("email")
    if not email:
        return None

    name = (claims.get("name") or "").strip() or "Unknown User"

    try:
        from app.infra.globals import get_redis_client
        from app.infra.identity.upsert import resolve_profile_upsert

        redis = get_redis_client()

        # Extract department_id from azp claim (glow-client-{department_id})
        department_ids: list[UUID] = []
        azp = claims.get("azp", "")
        if azp.startswith("glow-client-") and azp != "glow-client":
            try:
                dept_id_str = azp[len("glow-client-") :]
                department_ids = [UUID(dept_id_str)]
            except ValueError:
                pass

        result = await resolve_profile_upsert(
            pool,
            redis,
            name=name,
            emails=[email],
            role="guest",
            department_ids=department_ids or None,
        )
        logger.info(
            f"Auto-created guest profile {result.profile_id} for {email}"
            + (f" in department {department_ids[0]}" if department_ids else "")
        )
        return result.profile_id
    except Exception as e:
        logger.warning(f"Failed to auto-create guest profile for {email}: {e}")
        return None


MAX_EMULATION_DEPTH = 5


async def _find_active_grant_target(
    pool: asyncpg.Pool, profile_id: UUID
) -> EmulationChainLink | None:
    """Find a single active, unexpired, unconsumed emulation grant for a profile.

    Uses existing black boxes:
      - resolve_profile_identity_context → profiles_resource.id
      - search_grants(profiles_ids=...) → active grants for requester
      - search_grant_consumptions → filter out consumed grants
      - search_emulations(grant_ids=...) → target profiles_resource.id
      - search_profiles(profile_ids=...) → target profile_artifact.id

    Returns an EmulationChainLink or None.
    """
    from datetime import UTC, datetime

    from app.infra.globals import get_redis_client
    from app.infra.profile_identity_context import resolve_profile_identity_context
    from app.tools.artifacts.profile.search import search_profiles
    from app.tools.entries.emulations.search import search_emulations
    from app.tools.entries.grant_consumptions.search import (
        search_grant_consumptions,
    )
    from app.tools.entries.grants.search import search_grants

    redis = get_redis_client()

    context = await resolve_profile_identity_context(pool, profile_id, redis)
    if not context or not context.profiles_id:
        return None

    async with pool.acquire() as conn:
        grants = await search_grants(
            conn,
            profiles_ids=[context.profiles_id],
            active=True,
            limit=10,
        )

    if not grants:
        return None

    now = datetime.now(UTC)

    for grant in grants:
        if grant.expires_at <= now:
            continue

        async with pool.acquire() as conn:
            consumptions = await search_grant_consumptions(
                conn, grant_ids=[grant.id], limit=1
            )
        if consumptions:
            continue

        async with pool.acquire() as conn:
            emulations = await search_emulations(conn, grant_ids=[grant.id], limit=1)
        if not emulations or not emulations[0].profile_id:
            continue

        target_profiles_resource_id = emulations[0].profile_id

        async with pool.acquire() as conn:
            artifact_ids, _ = await search_profiles(
                conn,
                profile_ids=[target_profiles_resource_id],
                limit_count=1,
            )
        if artifact_ids:
            return EmulationChainLink(
                grant_id=grant.id,
                target_profile_id=artifact_ids[0],
            )

    return None


async def resolve_emulation_chain(
    pool: asyncpg.Pool, profile_id: UUID
) -> list[EmulationChainLink]:
    """Follow the emulation chain iteratively up to MAX_EMULATION_DEPTH.

    Starting from profile_id, finds active grants and follows targets:
      A → B → C (depth 2)

    Returns the full chain as a list of EmulationChainLink.
    Empty list means no active emulation.
    """
    chain: list[EmulationChainLink] = []
    current = profile_id
    visited: set[UUID] = set()

    try:
        while len(chain) < MAX_EMULATION_DEPTH:
            if current in visited:
                break
            visited.add(current)

            link = await _find_active_grant_target(pool, current)
            if link is None:
                break

            chain.append(link)
            current = link.target_profile_id

        if chain:
            logger.info(
                f"Emulation chain: {profile_id} → "
                + " → ".join(str(link.target_profile_id) for link in chain)
                + f" (depth {len(chain)})"
            )

        return chain
    except Exception as e:
        logger.warning(f"Failed to resolve emulation chain: {e}")
        return []


async def _get_or_create_session(conn: asyncpg.Connection, profile_id: UUID) -> UUID:
    """Get the most recent active session for a profile, or create one.

    profile_id is a profile_artifact.id. We must resolve to profiles_resource.id
    because profiles_sessions_connection.profiles_id references profiles_resource.
    """
    from app.tools.artifacts.profile.get import get_profiles

    # Resolve profile_artifact.id → profiles_resource.id
    profiles = await get_profiles(conn, [profile_id], profiles=True)
    if not profiles or not profiles[0].profile_ids:
        raise ValueError(
            f"No profiles_resource found for profile_artifact {profile_id}"
        )
    profiles_resource_id = profiles[0].profile_ids[0]

    # Check for recent active session (within last 24h)
    row = await conn.fetchrow(
        """
        SELECT se.id
        FROM sessions_entry se
        JOIN profiles_sessions_connection psc ON psc.session_id = se.id
        WHERE psc.profiles_id = $1
          AND se.active = true
          AND se.created_at > now() - interval '24 hours'
        ORDER BY se.created_at DESC
        LIMIT 1
        """,
        profiles_resource_id,
    )

    if row:
        return row["id"]

    # Create new session
    from app.tools.entries.sessions.create import create_session

    result = await create_session(conn, profile_id=profiles_resource_id)
    return result.id


# ---------------------------------------------------------------------------
# System session (for background tasks like health checks, metrics)
# ---------------------------------------------------------------------------


async def get_system_session_id(conn: asyncpg.Connection) -> UUID:
    """Get or create a system session for background tasks.

    This session is not tied to a user profile. It's used by the metrics
    collector, health check logger, and other server-internal processes.
    """
    global _system_session_id

    if _system_session_id is not None:
        # Verify it still exists
        exists = await conn.fetchval(
            "SELECT id FROM sessions_entry WHERE id = $1 AND active = true",
            _system_session_id,
        )
        if exists:
            return _system_session_id

    # Create a system session (no profile link needed).
    from app.tools.entries.sessions.create import create_session

    session_id = (await create_session(conn)).id

    _system_session_id = session_id
    logger.info(f"Created system session: {session_id}")
    return session_id


# ---------------------------------------------------------------------------
# Token extraction helpers
# ---------------------------------------------------------------------------


def extract_bearer_token(authorization: str | None) -> str | None:
    """Extract token from 'Bearer <token>' Authorization header."""
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip()


def extract_api_key(header_value: str | None) -> str | None:
    """Extract API key from X-Api-Key header."""
    if not header_value:
        return None
    return header_value.strip()
