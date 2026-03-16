"""Remove a guest socket from Redis."""

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def remove_guest_socket(socket_id: str) -> None:
    """Remove a guest socket from Redis."""
    redis_client = get_redis_client()
    if not redis_client:
        return

    try:
        result = await redis_client.srem("guest_sockets", socket_id)  # type: ignore
        _ = result  # Use result to avoid unused variable warning
    except Exception as e:
        logger.error(f"Redis error removing guest socket {socket_id}: {e}")
