"""Stream session management — Redis-backed sid lifecycle.

A stream session (sid) represents an authenticated connection context.
Entities are added via join (with permission checks) and removed via leave.
The SSE stream endpoint filters events to only those matching joined entities.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.infra.globals import get_redis_client

# Redis key layout:
#   stream_sid:{sid}:profile   → profile_id (str, TTL 24h)
#   stream_sid:{sid}:entities  → SET of "artifact:entity_id" (TTL 24h)

_TTL = 86400  # 24 hours


async def create_session(profile_id: UUID) -> str:
    """Create a new stream session and return its sid."""
    redis = get_redis_client()
    sid = str(uuid4())
    await redis.setex(f"stream_sid:{sid}:profile", _TTL, str(profile_id))
    return sid


async def destroy_session(sid: str) -> None:
    """Destroy a stream session and all its joined entities."""
    redis = get_redis_client()
    await redis.delete(f"stream_sid:{sid}:profile", f"stream_sid:{sid}:entities")


async def get_session_profile(sid: str) -> UUID | None:
    """Resolve the profile_id for a stream session, or None if expired/invalid."""
    redis = get_redis_client()
    raw = await redis.get(f"stream_sid:{sid}:profile")
    if not raw:
        return None
    return UUID(raw.decode() if isinstance(raw, bytes) else raw)


async def join_entity(sid: str, artifact: str, entity_id: UUID) -> None:
    """Add an entity to the session's joined set."""
    redis = get_redis_client()
    key = f"stream_sid:{sid}:entities"
    await redis.sadd(key, f"{artifact}:{entity_id}")
    await redis.expire(key, _TTL)


async def leave_entity(sid: str, artifact: str, entity_id: UUID) -> None:
    """Remove an entity from the session's joined set."""
    redis = get_redis_client()
    await redis.srem(f"stream_sid:{sid}:entities", f"{artifact}:{entity_id}")


async def get_joined_entities(sid: str) -> set[str]:
    """Return the set of joined entity keys ("artifact:entity_id")."""
    redis = get_redis_client()
    members = await redis.smembers(f"stream_sid:{sid}:entities")
    return {m.decode() if isinstance(m, bytes) else m for m in members}


async def is_entity_joined(sid: str, artifact: str, entity_id: UUID) -> bool:
    """Check if a specific entity is in the session's joined set."""
    redis = get_redis_client()
    return await redis.sismember(
        f"stream_sid:{sid}:entities", f"{artifact}:{entity_id}"
    )
