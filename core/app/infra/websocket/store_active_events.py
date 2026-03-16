"""Store the events iterator (async generator) to allow aclose() on cancel."""

from collections.abc import AsyncIterator

from app.infra.globals import get_active_results_dict


async def store_active_events(chat_id: str, events_iter: AsyncIterator[object]) -> None:
    """Store the events iterator (async generator) to allow aclose() on cancel."""
    active_results = get_active_results_dict()
    if chat_id not in active_results:
        active_results[chat_id] = {}
    active_results[chat_id]["events"] = events_iter
