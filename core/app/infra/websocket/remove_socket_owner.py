"""Remove a socket from the set of sockets owning a profile.

Returns ``True`` if this was the *last* socket for the profile —
callers use that signal to decide whether to mark the profile newly-
inactive (e.g. emit an activity row).

Two call shapes:
  - ``remove_socket_owner(profile_id, socket_id)`` — remove just one socket.
  - ``remove_socket_owner(profile_id)`` — remove the entire set (cleanup
    paths). Always returns ``True`` for that shape.

Redis is required. There is no in-memory fallback.
"""

from typing import Any

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def remove_socket_owner(
    profile_id: str,
    socket_id: str | None = None,
    *,
    redis_client: Any | None = None,
) -> bool:
    """Remove ``socket_id`` (or the whole set if ``socket_id`` is None).

    Returns:
        ``True`` if the profile has zero sockets after the removal
        (presence transitions present → absent), ``False`` otherwise.
    """
    redis_client = redis_client if redis_client is not None else get_redis_client()

    if socket_id is None:
        # Wholesale removal — pull the set of sids first so we can drop
        # each reverse-mapping key in lockstep.
        sids_bytes = await redis_client.smembers(f"socket_owners:{profile_id}")
        sids = [s.decode("utf-8") if isinstance(s, bytes) else s for s in sids_bytes]
        async with redis_client.pipeline() as pipe:
            pipe.delete(f"socket_owners:{profile_id}")
            for sid in sids:
                pipe.delete(f"socket_to_profile:{sid}")
            await pipe.execute()
        return True

    async with redis_client.pipeline() as pipe:
        pipe.srem(f"socket_owners:{profile_id}", socket_id)
        pipe.delete(f"socket_to_profile:{socket_id}")
        pipe.scard(f"socket_owners:{profile_id}")
        results = await pipe.execute()
    remaining = int(results[2] or 0)
    if remaining == 0:
        # Drop the empty set so it doesn't linger until TTL.
        await redis_client.delete(f"socket_owners:{profile_id}")
        return True
    return False
