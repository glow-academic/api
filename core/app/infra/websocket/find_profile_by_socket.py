"""Find the profile ID that owns a given socket id.

O(1) reverse lookup against the ``socket_to_profile:{sid}`` index that
``set_socket_owner`` keeps in lockstep with the forward set. If the
reverse index is somehow missing (e.g. a stray sid from before the
last deploy), we fall back to a bounded scan over ``socket_owners:*``.

Redis is required. There is no in-memory fallback.
"""

import contextvars

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

# Recursion guard so a Redis-via-logger callback can't reenter us
# infinitely if the lookup itself emits a log line that hits Redis.
_recursion_guard: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_recursion_guard", default=False
)


async def find_profile_by_socket(socket_id: str) -> str | None:
    """Find the profile ID that owns ``socket_id``, or None."""
    if _recursion_guard.get():
        return None

    _recursion_guard.set(True)
    try:
        redis_client = get_redis_client()

        # First try: direct O(1) lookup via the reverse index.
        profile_id_bytes = await redis_client.get(f"socket_to_profile:{socket_id}")
        if profile_id_bytes:
            return (
                profile_id_bytes.decode("utf-8")
                if isinstance(profile_id_bytes, bytes)
                else profile_id_bytes
            )

        # Fallback: scan SETs (rare — the reverse index normally covers
        # us). Bounded to keep tail latency safe.
        count = 0
        max_keys = 1000
        async for key in redis_client.scan_iter(match="socket_owners:*"):
            count += 1
            if count > max_keys:
                break
            if await redis_client.sismember(key, socket_id):
                k = key.decode("utf-8") if isinstance(key, bytes) else key
                return k.replace("socket_owners:", "")
        return None
    except Exception as e:
        # print rather than logger.error to avoid Redis-via-logger recursion
        print(f"Redis error finding profile by socket {socket_id}: {e}", flush=True)
        return None
    finally:
        _recursion_guard.set(False)
