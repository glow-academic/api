"""Remove an active run from Redis."""

from typing import Any

from app.infra.globals import get_redis_client


async def remove_active_run(chat_id: str, *, redis_client: Any | None = None) -> None:
    """Remove an active run from Redis."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    await redis_client.delete(f"active_run:{chat_id}")
