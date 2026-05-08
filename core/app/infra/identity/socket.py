"""Socket identity — store and resolve Identity for socket connections.

The socket analogue of middleware.py. At connect time, the full Identity
is stored in Redis. Input handlers call resolve_socket_identity(sid) to
get it back — same Identity object the HTTP middleware provides.
"""

from __future__ import annotations

import json
from uuid import UUID

from app.infra.globals import get_redis_client
from app.infra.identity.resolve_identity import Identity
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

_IDENTITY_TTL = 86400  # 24 hours, same as existing socket keys


async def store_socket_identity(sid: str, identity: Identity) -> None:
    """Store the full Identity in Redis for a socket connection."""
    redis = get_redis_client()
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
    await redis.setex(f"socket_identity:{sid}", _IDENTITY_TTL, data)


async def resolve_socket_identity(sid: str) -> Identity | None:
    """Resolve the Identity for a socket connection from Redis."""
    redis = get_redis_client()
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


async def remove_socket_identity(sid: str) -> None:
    """Remove the stored Identity for a socket connection."""
    redis = get_redis_client()
    await redis.delete(f"socket_identity:{sid}")
