"""Get the socket ID that owns a profile from Redis."""

from typing import Any

from app.infra.globals import get_redis_client, get_socket_owner_dict
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def get_socket_owner(
    profile_id: str,
    *,
    redis_client: Any | None = None,
    socket_owner: dict[str, str] | None = None,
) -> str | None:
    """Get the socket ID that owns a profile from Redis."""
    redis_client = redis_client if redis_client is not None else get_redis_client()
    socket_owner = socket_owner if socket_owner is not None else get_socket_owner_dict()
    if not redis_client:
        # Fallback to in-memory storage
        return socket_owner.get(profile_id)

    try:
        owner_sid = await redis_client.get(f"socket_owner:{profile_id}")
        return owner_sid.decode("utf-8") if owner_sid else None
    except Exception as e:
        logger.error(f"Redis error getting socket owner for profile {profile_id}: {e}")
        # Fallback to in-memory storage
        return socket_owner.get(profile_id)
