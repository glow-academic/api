"""Remove the socket ownership for a profile from Redis."""

from typing import Any

from app.infra.globals import get_redis_client, get_socket_owner_dict
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def remove_socket_owner(
    profile_id: str,
    *,
    redis_client: Any | None = None,
    socket_owner: dict[str, str] | None = None,
) -> None:
    """Remove the socket ownership for a profile from Redis.

    Removes both:
    - socket_owner:{profile_id} (forward mapping)
    - socket_to_profile:{socket_id} (reverse mapping)
    """
    redis_client = redis_client if redis_client is not None else get_redis_client()
    socket_owner = socket_owner if socket_owner is not None else get_socket_owner_dict()
    if not redis_client:
        # Fallback to in-memory storage
        socket_owner.pop(profile_id, None)
        return

    try:
        # First, get the socket_id so we can remove the reverse index
        socket_id_bytes = await redis_client.get(f"socket_owner:{profile_id}")
        socket_id = socket_id_bytes.decode("utf-8") if socket_id_bytes else None

        # Use pipeline to remove both keys atomically
        async with redis_client.pipeline() as pipe:
            pipe.delete(f"socket_owner:{profile_id}")
            if socket_id:
                pipe.delete(f"socket_to_profile:{socket_id}")
            await pipe.execute()
    except Exception as e:
        logger.error(f"Redis error removing socket owner for profile {profile_id}: {e}")
        # Fallback to in-memory storage
        socket_owner.pop(profile_id, None)
