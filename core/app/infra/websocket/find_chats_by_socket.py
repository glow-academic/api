"""Find all chat IDs for a socket ID.

O(1) reverse lookup against the ``socket_chats:{sid}`` index that
``set_active_connection`` keeps in lockstep with the forward
``active_connection:{chat_id}`` sets. Before PERF2 this did an unbounded
``scan_iter`` over every ``active_connection:*`` key plus a per-key
SISMEMBER on every disconnect — O(total active chats) work per disconnect.
If the reverse index is somehow missing (e.g. a stray sid from before the
last deploy that pre-dates the index), we fall back to a bounded scan.
"""

from app.infra.globals import get_redis_client


async def find_chats_by_socket(socket_id: str) -> list[str]:
    """Find all chat IDs for a socket ID (O(1) via the reverse index)."""
    redis_client = get_redis_client()

    # First try: direct O(1) lookup via the reverse index.
    members = await redis_client.smembers(f"socket_chats:{socket_id}")
    if members:
        return [
            m.decode("utf-8") if isinstance(m, bytes) else m for m in members
        ]

    # Fallback: bounded scan of the forward sets (rare — the reverse index
    # normally covers us). Bounded to keep tail latency safe.
    chats: list[str] = []
    count = 0
    max_keys = 1000
    async for key in redis_client.scan_iter(match="active_connection:*"):
        count += 1
        if count > max_keys:
            break
        if await redis_client.sismember(key, socket_id):
            k = key.decode("utf-8") if isinstance(key, bytes) else key
            chats.append(k.replace("active_connection:", ""))
    return chats
