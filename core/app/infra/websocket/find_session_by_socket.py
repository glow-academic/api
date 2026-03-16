"""Find the session ID for a socket ID."""

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def find_session_by_socket(socket_id: str) -> str | None:
    """Find the session ID for a socket ID via Redis.

    The session_id is stored at connect time in socket_session:{sid}.
    """
    redis_client = get_redis_client()
    if not redis_client:
        return None

    try:
        session_id_bytes = await redis_client.get(f"socket_session:{socket_id}")
        if session_id_bytes:
            return session_id_bytes.decode("utf-8")
        return None
    except Exception as e:
        print(f"Redis error finding session by socket {socket_id}: {e}", flush=True)
        return None
