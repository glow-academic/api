"""Add a guest socket to Redis."""

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def add_guest_socket(socket_id: str) -> None:
    """Add a guest socket to Redis."""
    redis_client = get_redis_client()
    if not redis_client:
        return

    try:
        result = await redis_client.sadd("guest_sockets", socket_id)  # type: ignore
        _ = result  # Use result to avoid unused variable warning
    except Exception as e:
        logger.error(f"Redis error adding guest socket {socket_id}: {e}")
