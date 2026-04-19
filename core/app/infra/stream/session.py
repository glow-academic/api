"""Stream session management — Redis-backed group subscriptions.

Profiles subscribe to groups. The SSE stream endpoint delivers events
for all groups a profile has joined.

Redis key layout:
  stream_groups:{profile_id} → SET of group_id strings (TTL 24h)
"""

from __future__ import annotations

from uuid import UUID

from app.infra.globals import get_redis_client

_TTL = 86400  # 24 hours


def _key(profile_id: str) -> str:
    return f"stream_groups:{profile_id}"


async def join_group(profile_id: str, group_id: UUID) -> None:
    """Subscribe a profile to a group's events."""
    redis = get_redis_client()
    key = _key(profile_id)
    await redis.sadd(key, str(group_id))
    await redis.expire(key, _TTL)


async def leave_group(profile_id: str, group_id: UUID) -> None:
    """Unsubscribe a profile from a group's events."""
    redis = get_redis_client()
    await redis.srem(_key(profile_id), str(group_id))


async def get_joined_groups(profile_id: str) -> set[UUID]:
    """Return all group_ids this profile is subscribed to."""
    redis = get_redis_client()
    members = await redis.smembers(_key(profile_id))
    result: set[UUID] = set()
    for m in members:
        raw = m.decode() if isinstance(m, bytes) else m
        try:
            result.add(UUID(raw))
        except ValueError:
            pass
    return result


# ---------------------------------------------------------------------------
# Legacy functions — kept for backward compat during migration
# ---------------------------------------------------------------------------


async def create_session(profile_id: UUID) -> str:
    """Legacy: create a stream session. Use join_group instead."""
    from uuid import uuid4
    redis = get_redis_client()
    sid = str(uuid4())
    await redis.setex(f"stream_sid:{sid}:profile", _TTL, str(profile_id))
    return sid


async def destroy_session(sid: str) -> None:
    """Legacy: destroy a stream session."""
    redis = get_redis_client()
    await redis.delete(f"stream_sid:{sid}:profile", f"stream_sid:{sid}:entities")


async def get_session_profile(sid: str) -> UUID | None:
    """Legacy: resolve profile_id for a stream session."""
    redis = get_redis_client()
    raw = await redis.get(f"stream_sid:{sid}:profile")
    if not raw:
        return None
    return UUID(raw.decode() if isinstance(raw, bytes) else raw)


async def join_entity(sid: str, artifact: str, entity_id: UUID) -> None:
    """Legacy: add entity to session. Use join_group instead."""
    redis = get_redis_client()
    key = f"stream_sid:{sid}:entities"
    await redis.sadd(key, f"{artifact}:{entity_id}")
    await redis.expire(key, _TTL)


async def leave_entity(sid: str, artifact: str, entity_id: UUID) -> None:
    """Legacy: remove entity from session."""
    redis = get_redis_client()
    await redis.srem(f"stream_sid:{sid}:entities", f"{artifact}:{entity_id}")


async def get_joined_entities(sid: str) -> set[str]:
    """Legacy: return joined entity keys."""
    redis = get_redis_client()
    members = await redis.smembers(f"stream_sid:{sid}:entities")
    return {m.decode() if isinstance(m, bytes) else m for m in members}


async def is_entity_joined(sid: str, artifact: str, entity_id: UUID) -> bool:
    """Legacy: check if entity is joined."""
    redis = get_redis_client()
    return await redis.sismember(
        f"stream_sid:{sid}:entities", f"{artifact}:{entity_id}"
    )
