"""Get one socket ID for an active chat connection from Redis."""

from typing import Any

from app.infra.globals import get_redis_client


async def get_active_connection(
    chat_id: str, *, redis_client: Any | None = None
) -> str | None:
    """Return one (arbitrary) socket id from the active connection set."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    sids = await redis_client.smembers(f"active_connection:{chat_id}")
    if not sids:
        return None
    sid = next(iter(sids))
    return sid.decode("utf-8") if isinstance(sid, bytes) else sid
