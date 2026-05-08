"""Add a socket to the set of sockets owning a profile.

Multiple sockets per profile are allowed (multi-tab, multi-device, debug
panels). Each profile maps to a Redis SET of sids; clients connect, join
the profile-id room, and receive every event the API broadcasts there.

Returns ``True`` if this is the *first* socket for the profile — callers
use that signal to decide whether to mark the profile newly-active.

Redis is required. There is no in-memory fallback: distributed presence
state must be authoritative across replicas.
"""

from typing import Any

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def set_socket_owner(
    profile_id: str,
    socket_id: str,
    *,
    redis_client: Any | None = None,
) -> bool:
    """Add ``socket_id`` to the set of sockets owning ``profile_id``.

    Maintains two Redis structures:
      - ``socket_owners:{profile_id}`` — SET of sids
      - ``socket_to_profile:{socket_id}`` — STRING reverse mapping (O(1)
        ``find_profile_by_socket``)

    Returns:
        ``True`` if this is the first socket attached to the profile
        (presence transitions absent → present), ``False`` otherwise.
    """
    redis_client = redis_client if redis_client is not None else get_redis_client()

    async with redis_client.pipeline() as pipe:
        pipe.sadd(f"socket_owners:{profile_id}", socket_id)
        pipe.expire(f"socket_owners:{profile_id}", 86400)
        pipe.setex(f"socket_to_profile:{socket_id}", 86400, profile_id)
        results = await pipe.execute()
    # SADD returns the number of new elements; if SCARD now equals SADD's
    # return value, this socket was the first for the profile.
    added = int(results[0] or 0)
    if added == 0:
        return False
    size = await redis_client.scard(f"socket_owners:{profile_id}")
    return int(size or 0) == added
