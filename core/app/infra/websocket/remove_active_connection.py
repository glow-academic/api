"""Remove a socket from an active chat connection set in Redis."""

from typing import Any

from app.infra.globals import get_redis_client


async def remove_active_connection(
    chat_id: str, socket_id: str, *, redis_client: Any | None = None
) -> None:
    """Remove socket from the chat connection set; drop the key when empty.

    Also drops the ``chat_id`` from the reverse ``socket_chats:{sid}`` index
    so the two stay in lockstep (PERF2). Atomicity note: the forward
    ``srem`` is the source of truth for presence/disconnect correctness
    (D1/#338); the reverse-index ``srem`` is a best-effort cleanup of an
    index entry that also carries its own 1h TTL, so a missed cleanup
    self-heals and never resurrects presence.
    """
    redis_client = redis_client if redis_client is not None else get_redis_client()
    key = f"active_connection:{chat_id}"
    await redis_client.srem(key, socket_id)
    if await redis_client.scard(key) == 0:
        await redis_client.delete(key)

    # Keep the reverse index in lockstep.
    await redis_client.srem(f"socket_chats:{socket_id}", chat_id)
