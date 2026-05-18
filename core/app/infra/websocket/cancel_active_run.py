"""Cancel an active run using cooperative cancellation."""

from app.infra.globals import get_redis_client
from app.infra.websocket.get_active_run import get_active_run
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def cancel_active_run(chat_id: str) -> bool:
    """Cancel an active run using cooperative cancellation."""
    redis_client = get_redis_client()
    run_id = await get_active_run(chat_id)
    if not run_id:
        return False
    # 5-minute TTL — runs that take longer than this should never need a
    # late-arriving cancellation marker anyway.
    await redis_client.setex(f"cancel_run:{run_id}", 300, "1")
    logger.info(f"Cancelled active run {run_id} for chat {chat_id}")
    return True
