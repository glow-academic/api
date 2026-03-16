"""Check if a socket is a guest socket."""

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def is_guest_socket(socket_id: str) -> bool:
    """Check if a socket is a guest socket."""
    redis_client = get_redis_client()
    if not redis_client:
        return False

    try:
        result = await redis_client.sismember("guest_sockets", socket_id)  # type: ignore
        return bool(result)
    except Exception as e:
        logger.error(f"Redis error checking guest socket {socket_id}: {e}")
        return False
