"""Set the socket ID that owns a profile in Redis."""

from typing import Any

from app.infra.globals import get_redis_client, get_socket_owner_dict
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def set_socket_owner(
    profile_id: str,
    socket_id: str,
    *,
    redis_client: Any | None = None,
    socket_owner: dict[str, str] | None = None,
) -> None:
    """Set the socket ID that owns a profile in Redis.

    Sets both:
    - socket_owner:{profile_id} → socket_id (forward mapping)
    - socket_to_profile:{socket_id} → profile_id (reverse mapping for O(1) lookup)
    """
    redis_client = redis_client if redis_client is not None else get_redis_client()
    socket_owner = socket_owner if socket_owner is not None else get_socket_owner_dict()
    if not redis_client:
        # Fallback to in-memory storage
        socket_owner[profile_id] = socket_id
        return

    try:
        # Use pipeline to set both keys atomically
        async with redis_client.pipeline() as pipe:
            # Set forward mapping: profile_id → socket_id
            pipe.setex(f"socket_owner:{profile_id}", 86400, socket_id)
            # Set reverse mapping: socket_id → profile_id (for O(1) lookup)
            pipe.setex(f"socket_to_profile:{socket_id}", 86400, profile_id)
            await pipe.execute()
    except Exception as e:
        logger.error(f"Redis error setting socket owner for profile {profile_id}: {e}")
        # Fallback to in-memory storage
        socket_owner[profile_id] = socket_id
