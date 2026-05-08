"""Find all chat IDs for a socket ID."""

from app.infra.globals import get_redis_client


async def find_chats_by_socket(socket_id: str) -> list[str]:
    """Find all chat IDs for a socket ID."""
    redis_client = get_redis_client()
    chats: list[str] = []
    async for key in redis_client.scan_iter(match="active_connection:*"):
        if await redis_client.sismember(key, socket_id):
            k = key.decode("utf-8") if isinstance(key, bytes) else key
            chats.append(k.replace("active_connection:", ""))
    return chats
