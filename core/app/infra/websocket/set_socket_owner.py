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

# Atomic first-socket detection. SADD then SCARD in ONE server-side script so
# the size is read against the SAME set state the SADD produced — no
# interleaving from a concurrent connect. Returns 1 iff THIS call BOTH added a
# new sid AND that add brought the set to size 1 (i.e. this socket is the first
# for the profile); 0 otherwise.
#
# Why not "scard == added" after a pipeline (the old code): two tabs into an
# empty set each SADD a distinct new sid (both added=1), then both SCARD in
# separate round-trips see size=2 → 2==1 is False for BOTH → neither is_first
# → presence/activity never written. The check must be atomic with the add.
#
# The ``added == 1`` guard preserves the original contract that a re-add of an
# already-present sid is never "first" (SADD returns 0 → no presence transition).
_FIRST_SOCKET_LUA = """
local added = redis.call('SADD', KEYS[1], ARGV[1])
redis.call('EXPIRE', KEYS[1], ARGV[2])
if added == 1 and redis.call('SCARD', KEYS[1]) == 1 then
    return 1
end
return 0
"""


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

    # Reverse mapping (socket → profile) is independent of first-socket
    # detection; write it directly.
    await redis_client.setex(f"socket_to_profile:{socket_id}", 86400, profile_id)

    # Atomic add + first-socket detection (see _FIRST_SOCKET_LUA). Doing the
    # SCARD inside the same server-side script — against the state THIS add
    # produced — is what makes concurrent multi-tab connects resolve to exactly
    # one first-socket winner.
    is_first = await redis_client.eval(
        _FIRST_SOCKET_LUA,
        1,
        f"socket_owners:{profile_id}",
        socket_id,
        86400,
    )
    return int(is_first or 0) == 1
