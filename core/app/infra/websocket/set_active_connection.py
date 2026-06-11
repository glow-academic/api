"""Add a socket ID to an active chat connection set in Redis."""

from typing import Any

from app.infra.globals import get_redis_client


async def set_active_connection(
    chat_id: str, socket_id: str, *, redis_client: Any | None = None
) -> None:
    """Add the socket ID to the active chat connections (1-hour TTL).

    Maintains a reverse ``socket_chats:{sid}`` SET in lockstep with the
    forward ``active_connection:{chat_id}`` set so that, on disconnect,
    ``find_chats_by_socket`` can resolve a socket's chats with an O(1)
    SMEMBERS instead of an unbounded keyspace SCAN (PERF2).
    """
    redis_client = redis_client if redis_client is not None else get_redis_client()
    key = f"active_connection:{chat_id}"
    await redis_client.sadd(key, socket_id)
    await redis_client.expire(key, 3600)

    # Reverse index: socket -> chats. Same TTL as the forward set so it
    # self-cleans if a disconnect is ever missed.
    rev_key = f"socket_chats:{socket_id}"
    await redis_client.sadd(rev_key, chat_id)
    await redis_client.expire(rev_key, 3600)
