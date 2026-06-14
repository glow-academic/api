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

import asyncio
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import asyncpg
import requests
from jose import jwt
from redis.asyncio import Redis

from app.infra.identity.keycloak_sync import get_idp_public_url
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

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
            # O2: a JWKS fetch failure means the auth subsystem is degrading
            # (Keycloak unreachable / endpoint down). This loop is TTL-gated
            # (at most once per _JWKS_TTL window), not hot-path noise, so log at
            # WARNING with the URL + error class so the degradation is visible to
            # operators rather than buried at debug.
            logger.warning(
                "JWKS fetch failed from %s (%s): %s",
                jwks_url,
                type(e).__name__,
                e,
            )
            continue

    # Also include the built-in default-idp keys from the canonical infra module.
    try:
        from app.infra.identity.jwks import get_jwks as get_default_idp_jwks

        default_keys = get_default_idp_jwks().get("keys", [])
        all_keys.extend(default_keys)
    except Exception as e:
        # O2: the built-in default-idp keys are the fallback verification path;
        # losing them is also auth-subsystem degradation, so warn (not debug).
        logger.warning(
            "Failed to load default-idp JWKS (%s): %s", type(e).__name__, e
        )

    if all_keys:
        _jwks_cache["keys"] = all_keys
        _jwks_cache["ts"] = now
        return all_keys

    # Fall back to cached keys if available
    if _jwks_cache["keys"] is not None:
        # O2: surface that we're running on stale cached keys, and from where.
        # During a key rotation this is the window where newly-issued tokens
        # start failing verification, so operators need this to be visible (not
        # a context-free message).
        logger.warning(
            "Failed to refresh JWKS from %s — falling back to cached keys "
            "(auth verification may fail for tokens signed by rotated keys)",
            ", ".join(urls_to_try) or "<no reachable endpoints>",
        )
        # Refresh the cache timestamp on fallback. Without this the stale `ts`
        # keeps `now - ts > _JWKS_TTL` true, so a slow/unavailable Keycloak is
        # re-hit on *every* request (each one paying the full blocking fetch).
        # Bumping `ts` bounds the retry to at most once per TTL window — the
        # TTL value (and thus refresh cadence) is unchanged.
        _jwks_cache["ts"] = now
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

        # Pin the verification algorithm to RS256. Both legitimate signers —
        # Keycloak's realm key and the built-in default-idp (see
        # default_idp._build_id_and_access_tokens + jwks.py) — only ever issue
        # RS256-signed tokens. Deriving the algorithm from the attacker-
        # controlled token header (headers["alg"]) would delegate the entire
        # alg-confusion defense to python-jose internals; pin it here so an
        # `alg=none` or HS-vs-RS confusion token can never reach a verifying
        # path regardless of the installed jose version.
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={
                "verify_at_hash": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )

        # Validate issuer — accept Keycloak and default-idp issuers. A token
        # with a missing/empty `iss` is rejected: every legitimate signer
        # always sets `iss`, so an absent issuer is never a valid token.
        token_issuer = claims.get("iss", "")
        expected_issuers = [
            KEYCLOAK_ISSUER,
            f"{KEYCLOAK_INTERNAL_URL}/auth/realms/{KEYCLOAK_REALM}",
            "http://localhost:8080/auth/realms/master",
            _default_idp_base,
        ]

        if not token_issuer or not any(
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
    from app.infra.server_timing import timed

    with timed("jwt_verify"):
        # verify_jwt is synchronous and `_get_jwks` (which it may call on a
        # cold/expired cache) does a *blocking* `requests.get` to Keycloak.
        # Running it inline would freeze the asyncio event loop for the whole
        # process whenever Keycloak is slow — stalling every concurrent
        # request, not just this auth call. Offload it to a worker thread so a
        # slow JWKS fetch can never block the loop. The verification logic
        # itself (signature/alg-pin/iss checks) is unchanged.
        claims = await asyncio.to_thread(verify_jwt, token)

    # Resolve profile_id
    with timed("profile_lookup"):
        profile_id = await _resolve_profile_id(claims, pool)

    # Auto-create guest profile if email exists but no profile found
    if profile_id is None:
        with timed("guest_create"):
            profile_id = await _auto_create_guest_profile(claims, pool)

    if profile_id is None:
        raise ValueError(
            f"No profile found for token claims (email={claims.get('email')})"
        )

    # Check for active emulation override (admin viewing as another profile)
    actor_profile_id: UUID | None = None
    is_emulation = False
    emulation_depth = 0
    with timed("emulation"):
        chain = await resolve_emulation_chain(pool, profile_id)
    if chain:
        actor_profile_id = profile_id
        profile_id = chain[-1].target_profile_id
        is_emulation = True
        emulation_depth = len(chain)

    # Get or create session for the effective profile
    with timed("session"):
        async with pool.acquire() as conn:
            session_id = await get_or_create_session(conn, profile_id)

    return Identity(
        profile_id=profile_id,
        session_id=session_id,
        email=claims.get("email"),
        role=claims.get("role"),
        is_emulation=is_emulation,
        actor_profile_id=actor_profile_id,
        emulation_depth=emulation_depth,
    )


_kc_admin_singleton: Any = None


def _get_keycloak_admin() -> Any:
    """Return a lazy module-level KeycloakAdmin instance.

    python-keycloak refreshes its own admin token, so a singleton is safe.
    Used by the sub-fallback in _resolve_profile_id for DCR-issued tokens
    that lack an email claim.
    """
    global _kc_admin_singleton
    if _kc_admin_singleton is None:
        from keycloak import KeycloakAdmin  # type: ignore

        _kc_admin_singleton = KeycloakAdmin(
            server_url=KEYCLOAK_INTERNAL_URL + "/auth/",
            username=os.getenv("KEYCLOAK_ADMIN", "admin"),
            password=os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin"),
            realm_name=KEYCLOAK_REALM,
            verify=False,
        )
    return _kc_admin_singleton


async def _email_from_keycloak_sub(sub: str) -> str | None:
    """Resolve a Keycloak user id (`sub` claim) to the user's email.

    Used when a token has no email claim (minimal DCR clients like Claude's
    MCP connector issue bare tokens with only sub/aud/iss/etc). Keycloak
    user records carry email (populated by keycloak_sync when glow profiles
    are synced). Cached briefly in redis to avoid hitting the admin API on
    every MCP request.
    """
    from app.infra.globals import get_redis_client

    redis = get_redis_client()
    cache_key = f"glow:kc_sub_email:{sub}"

    if redis is not None:
        try:
            cached = await redis.get(cache_key)
            if cached is not None:
                value = cached.decode() if isinstance(cached, bytes) else cached
                return value or None  # empty string = cached negative result
        except Exception:
            pass

    try:
        user = _get_keycloak_admin().get_user(user_id=sub)
        email = (user or {}).get("email") or ""
    except Exception:
        email = ""

    if redis is not None:
        try:
            await redis.set(cache_key, email, ex=60)
        except Exception:
            pass

    return email or None


async def _resolve_profile_id(
    claims: dict[str, Any], pool: asyncpg.Pool
) -> UUID | None:
    """Extract profile_id from JWT claims.

    Strategy:
    1. Direct profile_id claim (from default_idp tokens)
    2. Email claim → glow profile lookup (standard OIDC scopes)
    3. Keycloak sub → Keycloak user email → glow profile lookup
       (for DCR clients that omit the email scope)
    """
    # Strategy 1: Direct profile_id in claims (default_idp puts it there)
    direct_id = claims.get("profile_id")
    if direct_id:
        try:
            return UUID(direct_id)
        except ValueError:
            pass

    # Strategy 2: Email claim (fully-scoped OIDC clients put it there)
    # Strategy 3: Fetch email from Keycloak by sub when the token lacks it
    email = claims.get("email")
    sub = claims.get("sub")
    if not email and sub:
        email = await _email_from_keycloak_sub(sub)
    if not email:
        return None

    from app.tools.artifacts.profile.search import search_profiles

    # P4: the auth path resolves an EXACT email — use a case-insensitive
    # equality lookup instead of the substring search in search_emails
    # (`LIKE '%'||$1||'%'`), which forced a seq scan on every email-claim auth
    # and would also spuriously match substrings of another user's address.
    # The prior code matched case-insensitively (`e.email.lower() ==
    # email.lower()`), and emails are NOT normalized to lowercase at write
    # (create_email stores them verbatim), so we keep `LOWER(email) = LOWER($1)`
    # to preserve that behavior — served by the functional index
    # idx_emails_resource_lower_email (added in the report-15 migration), so it
    # is a seek, not a scan.
    async with pool.acquire() as conn:
        email_rows = await conn.fetch(
            "SELECT id FROM emails_resource "
            "WHERE LOWER(email) = LOWER($1) AND active = true",
            email,
        )

    matching_email_ids = [r["id"] for r in email_rows]
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

        # The azp claim only ever yields one department, so it is always the
        # primary. Without this, the profile gets no primary_departments
        # junction → no settings_id → tool_graph collapses → "No system/agent
        # configuration found." on first generate.
        primary_department_id = department_ids[0] if department_ids else None

        result = await resolve_profile_upsert(
            pool,
            redis,
            name=name,
            emails=[email],
            role="Guest",
            department_ids=department_ids or None,
            primary_department_id=primary_department_id,
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
            conn, redis,
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
                conn, redis, grant_ids=[grant.id], limit=1
            )
        if consumptions:
            continue

        async with pool.acquire() as conn:
            emulations = await search_emulations(conn, redis, grant_ids=[grant.id], limit=1)
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


_EMULATION_CACHE_KEY = "auth:emulation:{profile_id}"
_EMULATION_CACHE_TTL = 60  # seconds; explicit invalidation on write sites


def _emulation_cache_key(profile_id: UUID) -> str:
    return _EMULATION_CACHE_KEY.format(profile_id=profile_id)


async def invalidate_emulation_cache(profile_id: UUID) -> None:
    """Bust the cached emulation chain for ``profile_id``.

    Call from any write site that changes a profile's outgoing grants
    (grant create, emulation activate, unemulation). Best-effort: errors
    are swallowed since the TTL is the safety net.
    """
    from app.infra.globals import get_redis_client
    redis = get_redis_client()
    if redis is None:
        return
    try:
        await redis.delete(_emulation_cache_key(profile_id))
    except Exception:
        pass


async def resolve_emulation_chain(
    pool: asyncpg.Pool, profile_id: UUID
) -> list[EmulationChainLink]:
    """Follow the emulation chain iteratively up to MAX_EMULATION_DEPTH.

    Starting from profile_id, finds active grants and follows targets:
      A → B → C (depth 2)

    Returns the full chain as a list of EmulationChainLink.
    Empty list means no active emulation.

    Cached in Redis for ``_EMULATION_CACHE_TTL`` seconds; 99% of users
    have an empty chain so the cache hit is the dominant path. Write
    sites must call ``invalidate_emulation_cache`` for snappy UX —
    the TTL is the safety net.
    """
    import json
    from app.infra.globals import get_redis_client

    redis = get_redis_client()
    cache_key = _emulation_cache_key(profile_id)
    cached_raw: Any = None
    if redis is not None:
        try:
            cached_raw = await redis.get(cache_key)
        except Exception:
            cached_raw = None
    if cached_raw is not None:
        if isinstance(cached_raw, bytes):
            cached_raw = cached_raw.decode()
        try:
            data = json.loads(cached_raw)
            return [
                EmulationChainLink(
                    grant_id=UUID(link["grant_id"]),
                    target_profile_id=UUID(link["target_profile_id"]),
                )
                for link in data
            ]
        except Exception:
            # Bad cache entry — fall through to DB and overwrite below.
            pass

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

        # Cache the result (empty chain too — the common case).
        if redis is not None:
            try:
                payload = json.dumps([
                    {
                        "grant_id": str(link.grant_id),
                        "target_profile_id": str(link.target_profile_id),
                    }
                    for link in chain
                ])
                await redis.setex(cache_key, _EMULATION_CACHE_TTL, payload)
            except Exception:
                pass

        return chain
    except Exception as e:
        logger.warning(f"Failed to resolve emulation chain: {e}")
        return []


SESSION_IDLE_MINUTES = 10


async def get_or_create_session(conn: asyncpg.Connection, profile_id: UUID) -> UUID:
    """Get the current session for a profile, or mint a new one.

    Sessions are append-only — the ``active`` bool on ``sessions_entry``
    is reserved for soft-delete only and is **not** flipped on logout.
    Whether the latest session is still "current" is decided by two
    append-only signals:

      1. ``logouts_entry`` — an explicit row here means the caller
         clicked logout; we always mint a new session on the next
         request regardless of timing.
      2. ``activity_entry`` — the middleware writes one row per minute
         per profile while requests are flowing. If the latest
         activity (or the session's own created_at, for brand-new
         sessions with no activity yet) is older than
         ``SESSION_IDLE_MINUTES`` minutes, we mint a new session.

    profile_id is a profile_artifact.id. We must resolve to
    profiles_resource.id because profiles_sessions_connection.profiles_id
    references profiles_resource.
    """
    from app.tools.artifacts.profile.get import get_profiles

    from app.infra.globals import get_redis_client
    redis = get_redis_client()

    # Resolve profile_artifact.id → profiles_resource.id
    profiles = await get_profiles(conn, [profile_id], profiles=True)
    if not profiles or not profiles[0].profile_ids:
        raise ValueError(
            f"No profiles_resource found for profile_artifact {profile_id}"
        )
    profiles_resource_id = profiles[0].profile_ids[0]

    from app.tools.entries.activity.search import search_activity
    from app.tools.entries.logouts.search import search_logouts
    from app.tools.entries.sessions.create import create_session
    from app.tools.entries.sessions.search import search_sessions

    # search_sessions has a hedged-read cache (v1.0.31): fresh writes are
    # served from the per-id cache within its 1h window; older sessions
    # come from the MV. logouts/activity below still pass bypass_mv=True
    # because they don't have cache coverage yet.
    sessions = await search_sessions(
        conn, redis,
        profile_ids=[profiles_resource_id],
        active=True,
        limit=1,
    )
    if sessions:
        session = sessions[0]

        # Has the session been logged out? One row is enough — we
        # always mint a new session after any logout, regardless of
        # timing.
        logouts = await search_logouts(
            conn, redis,
            session_ids=[session.id],
            limit=1,
            bypass_mv=True,
        )
        if not logouts:
            # Idle gate. Latest activity row wins; fall back to the
            # session's own created_at for brand-new sessions whose
            # first activity ping hasn't landed yet (or got
            # throttled by the 60s SETNX in middleware).
            recent = await search_activity(
                conn, redis,
                session_ids=[session.id],
                limit=1,
            )
            last_seen = recent[0].created_at if recent else session.created_at
            cutoff = datetime.now(timezone.utc) - timedelta(
                minutes=SESSION_IDLE_MINUTES
            )
            if last_seen >= cutoff:
                return session.id

    # Mint a new session — either no prior, the latest was logged
    # out, or it idled past the threshold.
    result = await create_session(conn, redis, profile_id=profiles_resource_id)
    return result.id


# ---------------------------------------------------------------------------
# System session (for background tasks like health checks, metrics)
# ---------------------------------------------------------------------------


async def get_system_session_id(
    conn: asyncpg.Connection,
    redis: Redis,
) -> UUID:
    """Get or create a system session for background tasks.

    This session is not tied to a user profile. It's used by the metrics
    collector, health check logger, and other server-internal processes.

    ``redis`` must be passed by the caller. We do NOT reach into the
    app-global ``get_redis_client()`` here — that couples this helper to
    the FastAPI lifespan and makes it untestable outside the running
    server. Callers in the lifespan context can pass ``get_redis_client()``.
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

    session_id = (await create_session(conn, redis)).id

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
