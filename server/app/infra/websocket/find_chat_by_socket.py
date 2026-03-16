"""Find the chat ID for a socket ID."""

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def find_chat_by_socket(socket_id: str) -> str | None:
    """Find the chat ID for a socket ID."""
    redis_client = get_redis_client()
    if not redis_client:
        return None

    try:
        # Scan through all active connection keys to find the matching socket_id
        async for key in redis_client.scan_iter(match="active_connection:*"):
            is_member = await redis_client.sismember(key, socket_id)
            if is_member:
                chat_id = key.decode("utf-8").replace("active_connection:", "")
                return chat_id  # type: ignore
        return None
    except Exception as e:
        logger.error(f"Redis error finding chat by socket {socket_id}: {e}")
        return None
