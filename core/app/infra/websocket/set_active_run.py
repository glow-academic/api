"""Set the active run ID for a chat in Redis."""

from typing import Any

from app.infra.globals import get_redis_client


async def set_active_run(
    chat_id: str, run_id: str, *, redis_client: Any | None = None
) -> None:
    """Set the active run ID for a chat in Redis (2-hour TTL)."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    await redis_client.setex(f"active_run:{chat_id}", 7200, run_id)
