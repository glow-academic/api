"""Socket identity — store and resolve Identity for socket connections.

The socket analogue of middleware.py. At connect time, the full Identity
is stored in Redis. Input handlers call resolve_socket_identity(sid) to
get it back — same Identity object the HTTP middleware provides.
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from app.infra.globals import get_redis_client
from app.infra.identity.resolve_identity import Identity

logger = logging.getLogger(__name__)

_IDENTITY_TTL = 86400  # 24 hours, same as existing socket keys


async def store_socket_identity(sid: str, identity: Identity) -> None:
    """Store the full Identity in Redis for a socket connection."""
    redis = get_redis_client()
    if not redis:
        return

    data = json.dumps({
        "profile_id": str(identity.profile_id),
        "session_id": str(identity.session_id),
        "email": identity.email,
        "role": identity.role,
        "is_emulation": identity.is_emulation,
        "actor_profile_id": str(identity.actor_profile_id) if identity.actor_profile_id else None,
        "emulation_depth": identity.emulation_depth,
        "is_mcp": identity.is_mcp,
    })

    try:
        await redis.setex(f"socket_identity:{sid}", _IDENTITY_TTL, data)
    except Exception as e:
        logger.warning("Failed to store socket identity for sid %s: %s", sid, e)


async def resolve_socket_identity(sid: str) -> Identity | None:
    """Resolve the Identity for a socket connection from Redis."""
    redis = get_redis_client()
    if not redis:
        return None

    try:
        raw = await redis.get(f"socket_identity:{sid}")
        if not raw:
            return None

        data = json.loads(raw)
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
    except Exception as e:
        logger.warning("Failed to resolve socket identity for sid %s: %s", sid, e)
        return None


async def remove_socket_identity(sid: str) -> None:
    """Remove the stored Identity for a socket connection."""
    redis = get_redis_client()
    if not redis:
        return

    try:
        await redis.delete(f"socket_identity:{sid}")
    except Exception:
        pass
