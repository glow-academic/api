"""Check if a run has been cancelled."""

from app.infra.globals import get_redis_client
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def is_run_cancelled(run_id: str) -> bool:
    """Check if a run has been cancelled."""
    redis_client = get_redis_client()
    if not redis_client:
        return False

    try:
        cancelled = await redis_client.exists(f"cancel_run:{run_id}")
        return bool(cancelled)
    except Exception as e:
        logger.error(f"Redis error checking run cancellation for {run_id}: {e}")
        return False
