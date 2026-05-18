"""Call cancel() on the local Runner result if present."""

import asyncio

from app.infra.globals import get_active_results_dict
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def cancel_active_result(chat_id: str) -> bool:
    """Call cancel() on the local Runner result if present."""
    active_results = get_active_results_dict()
    entry = active_results.get(chat_id)
    if not entry:
        return False
    try:
        result = entry.get("result")
        events_iter = entry.get("events")

        # Best-effort: ask the Runner to cancel upstream generation
        if result is not None and hasattr(result, "cancel"):
            cancel_result = result.cancel()
            if asyncio.iscoroutine(cancel_result):
                await cancel_result

        # Close our local stream iterator so we stop yielding tokens immediately
        if events_iter is not None and hasattr(events_iter, "aclose"):
            await events_iter.aclose()
        return True
    except Exception as e:
        logger.error(f"Failed to cancel local result for chat {chat_id}: {e}")
        return False
