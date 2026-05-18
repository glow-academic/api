"""Read the set of socket IDs owning a profile.

A profile may have multiple concurrent sockets (multi-tab, multi-device,
debug panels). For per-event delivery, broadcast to ``room=profile_id``
via ``sio.emit`` — ``output.py`` does that for all canonical events.
This helper exists for the rare cases where caller code needs to
inspect or count the sockets directly.

Redis is required. There is no in-memory fallback.
"""

from typing import Any

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def get_socket_owners(
    profile_id: str,
    *,
    redis_client: Any | None = None,
) -> list[str]:
    """Return all socket IDs currently attached to ``profile_id``."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    members = await redis_client.smembers(f"socket_owners:{profile_id}")
    return [m.decode("utf-8") if isinstance(m, bytes) else m for m in members]


async def get_socket_owner(
    profile_id: str,
    *,
    redis_client: Any | None = None,
) -> str | None:
    """Return one (arbitrary) socket id for the profile, or None.

    Back-compat shim for HTTP callers that haven't moved to room-based
    broadcast yet. Prefer ``room=profile_id`` over picking a single sid.
    """
    sids = await get_socket_owners(profile_id, redis_client=redis_client)
    return sids[0] if sids else None
