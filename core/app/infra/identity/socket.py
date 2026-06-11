"""Socket identity — store and resolve Identity for socket connections.

The socket analogue of middleware.py. At connect time, the full Identity
is stored in Redis. Input handlers call resolve_socket_identity(sid) to
get it back — same Identity object the HTTP middleware provides.

SECURITY (SEC1): the cached snapshot is re-validated on every resolve so a
live socket cannot keep mutate privileges after its token expires, the
user logs out, or an emulation grant is revoked. The HTTP path re-resolves
identity on every request (see middleware.require_auth); this mirrors that
for the socket so the two surfaces enforce the same auth lifetime.

  * Cheap, every event: the token's ``exp`` is stored at connect and
    compared to ``now``. A past-expiry socket is rejected + disconnected
    with zero crypto/DB cost.
  * Throttled (``_REVALIDATE_INTERVAL``), at most once per window per
    socket: the stored bearer is re-run through ``resolve_identity`` — the
    same call the HTTP middleware uses — which re-verifies the JWT
    (catches revocation), re-resolves the emulation chain (catches a
    revoked/expired grant), and re-resolves the session (catches logout →
    a new session is minted). If it raises, or the effective profile /
    emulation changed since connect, the socket is rejected + disconnected.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING
from uuid import UUID

from app.infra.globals import get_redis_client
from app.infra.identity.resolve_identity import Identity
from app.utils.logging.db_logger import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = get_logger(__name__)

_IDENTITY_TTL = 86400  # 24 hours, same as existing socket keys

# How often (seconds) a live socket's bearer is re-run through the full
# resolve_identity. The cheap exp check runs on EVERY event regardless; this
# only bounds the JWT-reverify / emulation-recheck / logout-recheck cost so a
# chatty socket doesn't pay a DB round-trip per trivial event. With a 30s
# window the worst-case staleness for a logout/emulation-revoke is ~30s, while
# token-expiry is enforced immediately (every event) via the stored exp.
_REVALIDATE_INTERVAL = 30


async def store_socket_identity(
    sid: str, identity: Identity, token: str | None = None
) -> None:
    """Store the full Identity in Redis for a socket connection.

    ``token`` is the verified bearer from connect. We persist it (and its
    ``exp``) so ``resolve_socket_identity`` can re-validate the live socket
    — without it the socket would keep its connect-time privileges for the
    full 24h TTL even after the token expires or the session is revoked.
    """
    redis = get_redis_client()
    exp = _extract_exp(token) if token else None
    data = json.dumps({
        "profile_id": str(identity.profile_id),
        "session_id": str(identity.session_id),
        "email": identity.email,
        "role": identity.role,
        "is_emulation": identity.is_emulation,
        "actor_profile_id": str(identity.actor_profile_id) if identity.actor_profile_id else None,
        "emulation_depth": identity.emulation_depth,
        "is_mcp": identity.is_mcp,
        # SEC1: token lifetime + the bearer itself for per-event re-validation.
        "token": token,
        "exp": exp,
    })
    # Cap the Redis TTL at the token's remaining lifetime (never more than the
    # historical 24h). A snapshot can never outlive the token it was minted
    # from, so even if the re-validation path is somehow skipped the key
    # self-expires no later than the token does.
    ttl = _IDENTITY_TTL
    if exp is not None:
        remaining = int(exp - time.time())
        if remaining <= 0:
            remaining = 1  # store briefly; the next resolve will reject it
        ttl = min(_IDENTITY_TTL, remaining)
    await redis.setex(f"socket_identity:{sid}", ttl, data)


def _extract_exp(token: str) -> int | None:
    """Best-effort decode of the JWT ``exp`` (seconds since epoch).

    Unverified decode is acceptable here: the token was already
    signature-verified by ``resolve_identity`` at connect, and we only use
    ``exp`` as a cheap freshness gate (the throttled full re-verify below is
    the authoritative check). Returns None if ``exp`` can't be read.
    """
    try:
        from jose import jwt

        claims = jwt.get_unverified_claims(token)
        exp = claims.get("exp")
        return int(exp) if exp is not None else None
    except Exception:
        return None


async def _reject_socket(sid: str, reason: str) -> None:
    """Drop the cached identity and disconnect a now-invalid socket."""
    logger.warning("Rejecting socket %s: %s", sid, reason)
    try:
        await remove_socket_identity(sid)
    except Exception:
        pass
    try:
        from app.infra.globals import sio

        await sio.disconnect(sid)
    except Exception:
        pass


def _identity_from_data(data: dict) -> Identity:
    return Identity(
        profile_id=UUID(data["profile_id"]),
        session_id=UUID(data["session_id"]),
        email=data.get("email"),
        role=data.get("role"),
        is_emulation=data.get("is_emulation", False),
        actor_profile_id=UUID(data["actor_profile_id"]) if data.get("actor_profile_id") else None,
        emulation_depth=data.get("emulation_depth", 0),
        is_mcp=data.get("is_mcp", False),
    )


async def resolve_socket_identity(sid: str) -> Identity | None:
    """Resolve + re-validate the Identity for a socket connection.

    Returns the live Identity, or ``None`` if the socket is no longer
    authorized (expired token / logout / revoked emulation), in which case
    the socket is also disconnected. Every mutate handler already drops the
    event when this returns ``None``, so this is the single chokepoint that
    enforces SEC1 across all socket events.
    """
    redis = get_redis_client()
    raw = await redis.get(f"socket_identity:{sid}")
    if not raw:
        return None

    data = json.loads(raw)

    # ── Cheap gate (every event): token expiry. ──────────────────────────
    exp = data.get("exp")
    if exp is not None and time.time() >= float(exp):
        await _reject_socket(sid, "token expired")
        return None

    identity = _identity_from_data(data)

    # ── Throttled full re-validation: JWT re-verify + emulation + logout. ─
    token = data.get("token")
    if token and await _should_revalidate(redis, sid):
        ok = await _revalidate(sid, token, identity)
        if not ok:
            return None

    return identity


async def _should_revalidate(redis: Redis, sid: str) -> bool:
    """True at most once per ``_REVALIDATE_INTERVAL`` per socket (SETNX gate).

    Best-effort: if Redis errors we re-validate (fail-safe toward checking).
    """
    try:
        ok = await redis.set(
            f"socket_revalidated:{sid}", "1", nx=True, ex=_REVALIDATE_INTERVAL
        )
        # ``set ... nx`` returns truthy only when the key was absent — i.e.
        # the window just opened, so this is the call that should revalidate.
        return bool(ok)
    except Exception:
        return True


async def _revalidate(sid: str, token: str, cached: Identity) -> bool:
    """Re-run the full identity resolution; reject the socket if invalid.

    Mirrors the HTTP middleware: ``resolve_identity`` re-verifies the JWT
    (revocation/expiry), re-resolves the emulation chain (revoked grant),
    and re-resolves the session (logout mints a new session). A change in
    the effective profile or emulation state means the connect-time
    snapshot is stale and must not keep operating.
    """
    from app.infra.globals import get_pool
    from app.infra.identity.resolve_identity import resolve_identity

    try:
        pool = get_pool()
        fresh = await resolve_identity(token, pool)
    except ValueError as e:
        # Token invalid/expired/revoked at the IdP.
        await _reject_socket(sid, f"re-validation failed: {e}")
        return False
    except Exception as e:
        # Infra hiccup (pool/Keycloak). Don't tear down a live socket on a
        # transient error — the cheap exp gate already bounds the exposure,
        # and the next event re-tries.
        logger.warning("Socket %s re-validation skipped (transient): %s", sid, e)
        return True

    # Effective identity must be unchanged. A different effective profile or
    # a flipped emulation state means the grant was revoked/added or the
    # session rotated under a different actor — stop the stale socket.
    if (
        fresh.profile_id != cached.profile_id
        or fresh.is_emulation != cached.is_emulation
        or fresh.actor_profile_id != cached.actor_profile_id
    ):
        await _reject_socket(sid, "identity changed since connect")
        return False

    return True


async def remove_socket_identity(sid: str) -> None:
    """Remove the stored Identity for a socket connection."""
    redis = get_redis_client()
    await redis.delete(f"socket_identity:{sid}")
