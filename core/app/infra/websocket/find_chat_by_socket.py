"""Find the chat ID for a socket ID.

O(1) reverse lookup via the ``socket_chats:{sid}`` index (PERF2), with a
bounded scan fallback. Returns one chat id (the socket's first known chat).
"""

from app.infra.globals import get_redis_client


async def find_chat_by_socket(socket_id: str) -> str | None:
    """Find the chat ID for a socket ID (O(1) via the reverse index)."""
    redis_client = get_redis_client()

    # First try: direct O(1) lookup via the reverse index.
    members = await redis_client.smembers(f"socket_chats:{socket_id}")
    if members:
        m = next(iter(members))
        return m.decode("utf-8") if isinstance(m, bytes) else m

    # Fallback: bounded scan of the forward sets.
    count = 0
    max_keys = 1000
    async for key in redis_client.scan_iter(match="active_connection:*"):
        count += 1
        if count > max_keys:
            break
        if await redis_client.sismember(key, socket_id):
            k = key.decode("utf-8") if isinstance(key, bytes) else key
            return k.replace("active_connection:", "")
    return None
