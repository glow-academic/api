"""Stream session management — legacy entity-scoped helpers.

The per-(artifact, group_id) stream model used by every artifact wraps
``build_artifact_stream_impl`` directly with a group_id query param —
no Redis-backed group subscription is needed.

The helpers below are the legacy SID-keyed entity store still used by
``routes/test/join.py`` and ``routes/test/leave.py``; once those move to
the per-artifact shape this module can be deleted entirely.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.infra.globals import get_redis_client

_TTL = 86400  # 24 hours


# ---------------------------------------------------------------------------
# Legacy SID-keyed entity store (used by /test/join, /test/leave)
# ---------------------------------------------------------------------------


async def create_session(profile_id: UUID) -> str:
    """Legacy: create a stream session."""
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
    """Legacy: add entity to session."""
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
