"""Cancel an active run using cooperative cancellation."""

from app.infra.globals import get_redis_client
from app.infra.websocket.get_active_run import get_active_run
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def cancel_active_run(chat_id: str) -> bool:
    """Cancel an active run using cooperative cancellation."""
    redis_client = get_redis_client()
    if not redis_client:
        return False

    try:
        run_id = await get_active_run(chat_id)
        if not run_id:
            return False

        # Set cancellation flag with TTL (5 minutes)
        await redis_client.setex(f"cancel_run:{run_id}", 300, "1")
        logger.info(f"Successfully cancelled active run {run_id} for chat {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Error cancelling active run {chat_id}: {e}")
        return False
