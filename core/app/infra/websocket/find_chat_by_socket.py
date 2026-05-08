"""Find the chat ID for a socket ID."""

from app.infra.globals import get_redis_client


async def find_chat_by_socket(socket_id: str) -> str | None:
    """Find the chat ID for a socket ID."""
    redis_client = get_redis_client()
    async for key in redis_client.scan_iter(match="active_connection:*"):
        if await redis_client.sismember(key, socket_id):
            k = key.decode("utf-8") if isinstance(key, bytes) else key
            return k.replace("active_connection:", "")
    return None
