"""Get the active run ID for a chat from Redis."""

from typing import Any

from app.infra.globals import get_redis_client


async def get_active_run(
    chat_id: str, *, redis_client: Any | None = None
) -> str | None:
    """Get the active run ID for a chat from Redis."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    run_id = await redis_client.get(f"active_run:{chat_id}")
    if not run_id:
        return None
    return run_id.decode("utf-8") if isinstance(run_id, bytes) else run_id
